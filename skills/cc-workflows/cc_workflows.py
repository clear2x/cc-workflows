#!/usr/bin/env python3
"""
workflow.py — 多 Agent 动态工作流调度器
基于 claude -p 实现：12 种执行模式（6 个 CLI 原语 + 6 个官方 workflow pattern）。

CLI 原语:
  agents, run, pipeline, branch, parallel, loop, sessions

官方 workflow pattern（与 Anthropic 博客对齐）:
  classify (Classify-and-act)
  fanout  (Fan-out-and-synthesize)
  verify  (Adversarial verification)
  genfilter (Generate-and-filter)
  tournament (Tournament)
  loop_until (Loop until done)

用法:
  python3 workflow.py agents
  python3 workflow.py run "任务描述" --agent general-purpose
  python3 workflow.py pipeline --step "探索:列出所有 .py 文件" --agent Explore ...
  python3 workflow.py parallel --task "分析 a.py" --agent Explore --name a ...
  python3 workflow.py loop "Step 1: list files\nStep 2: report" --max-steps 100
  python3 workflow.py classify "Classify bug: security or perf?" \
      --class-security "audit..." --class-performance "profile..." --default "general..."
  python3 workflow.py fanout "Analyze all files" \
      --subtask "Check auth.py" --synthesize "Combine findings"
  python3 workflow.py verify "Implement feature X" --rubric "Must have tests"
  python3 workflow.py genfilter "Generate 5 names" --count 5 --filter-top 3
  python3 workflow.py tournament "Implement LRU cache" --contestants 3
  python3 workflow.py loop_until "Fix failing tests" \
      --stop-condition "All pytest pass" --max-iterations 10

环境:
  - 需要 claude CLI v2.1.168+ 已安装
  - 需要登录状态 (ANTHROPIC_API_KEY)
  - 支持代理 (环境变量由 ~/.claude/settings.json 提供)
"""

import subprocess
import json
import sys
import os
import time
import re
import fcntl
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, List, Dict

# ── 基础工具函数 ──────────────────────────────────────
def _safe_int(val: str, name: str = "参数", default: int = 0) -> int:
    """安全的 int 转换，失败时给出友好错误"""
    try:
        return int(val)
    except (ValueError, TypeError):
        print(f"⚠️ {name} 应为整数，收到 '{val}'，使用默认值 {default}")
        return default


def _detect_project_dir() -> Path:
    """自动检测 git root，失败则回退到当前目录"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


# ── 配置 ──────────────────────────────────────────────
MAX_TURNS = 12
MAX_STEPS = 100
STATE_FILE = Path("/tmp/claude_orchestrator_state.json")
PROGRESS_FILE = Path("/tmp/cc-workflows-progress.json")
PROJECT_DIR = _detect_project_dir()
WORKTREE_BASE = Path("/tmp/orchestrator-worktrees")
CLAUDE_TIMEOUT = 300


# ── 进度反馈 ──────────────────────────────────────────
def write_progress(progress: dict):
    """写入进度文件，供 Claude Code 后台轮询读取。完成时传 mode=None 清理。"""
    if progress.get("_cleanup"):
        PROGRESS_FILE.unlink(missing_ok=True)
        return
    progress["updated_at"] = time.strftime("%H:%M:%S")
    with open(PROGRESS_FILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(progress, f, indent=2, ensure_ascii=False)
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


def clear_progress():
    """任务完成后清理进度文件"""
    PROGRESS_FILE.unlink(missing_ok=True)


# ── 基础执行 ──────────────────────────────────────────
def run_claude(
    prompt: str,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    model: Optional[str] = None,
    max_turns: int = MAX_TURNS,
    output_format: str = "json",
    cwd: Optional[str] = None,
) -> dict:
    """执行 claude -p 并返回结构化结果"""
    cmd = [
        "claude", "-p",
        prompt,
        "--dangerously-skip-permissions",
        "--allowedTools", "Read,Write,Edit,Bash,Grep,Glob,TodoWrite",
        "--max-turns", str(max_turns),
        "--output-format", output_format,
    ]
    if session_id:
        cmd += ["--resume", session_id]
    if agent:
        cmd += ["--agent", agent]
    if model:
        cmd += ["--model", model]

    env = os.environ.copy()
    env.pop("CLAUDE_CODE_AUTO_COMPACT", None)

    run_cwd = cwd or str(PROJECT_DIR)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT,
            cwd=run_cwd,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "error": True,
            "stderr": f"claude 命令超时 ({CLAUDE_TIMEOUT}s)",
            "stdout": "",
        }

    # Parse output FIRST, regardless of return code.
    # claude -p returns non-zero for max_turns, permission denials, etc.,
    # but stdout may still contain valid JSON with assistant text blocks.
    events = _parse_claude_output(result.stdout)
    last_result = next((e for e in events if isinstance(e, dict) and e.get("type") == "result"), None)

    # If returncode != 0 but we have valid parsed output, treat as soft error
    # (e.g. max_turns reached — still extract whatever text we got).
    # Only hard-fail if stdout is empty or completely unparseable.
    if result.returncode != 0 and not events:
        return {
            "error": True,
            "stderr": result.stderr[:2000],
            "stdout": result.stdout[:500],
        }
    last_result = next((e for e in events if isinstance(e, dict) and e.get("type") == "result"), None)

    output = ""
    model_used = None
    if last_result:
        output = last_result.get("result") or ""
        if not output.strip():
            text_parts = []
            for e in events:
                if isinstance(e, dict) and e.get("type") == "assistant":
                    content = e.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
            output = "\n".join(text_parts).strip()

        model_used = last_result.get("model")
        if not model_used:
            mu = last_result.get("modelUsage", {})
            if isinstance(mu, dict) and mu:
                model_used = list(mu.keys())[0]

    if not last_result and not output:
        return {"error": True, "stderr": "未找到 result 事件或 assistant 文本", "stdout": result.stdout[:500]}

    return {
        "error": result.returncode != 0,  # True for max_turns etc, but we still return output
        "soft_error": result.returncode != 0 and last_result and last_result.get("subtype") in ("error_max_turns",),
        "session_id": (last_result or {}).get("session_id"),
        "stop_reason": (last_result or {}).get("stop_reason"),
        "num_turns": (last_result or {}).get("num_turns", 0),
        "total_cost_usd": (last_result or {}).get("total_cost_usd", 0),
        "output": output,
        "model": model_used,
    }


def _parse_claude_output(stdout: str):
    """解析 claude --output-format json 的多行/数组输出"""
    events = []
    stripped = stdout.strip()
    if not stripped:
        return events
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            events = parsed
        elif isinstance(parsed, dict):
            events = [parsed]
        return events
    except (json.JSONDecodeError, ValueError):
        pass
    for line in stripped.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


# ── 状态管理 ──────────────────────────────────────────
def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)  # 共享锁（读）
            data = json.loads(f.read())
            fcntl.flock(f, fcntl.LOCK_UN)
            return data
    except (json.JSONDecodeError, ValueError):
        return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # 排他锁（写）
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


# ── 模式 1: 查看可用 agent ───────────────────────────
def cmd_agents():
    """列出所有可用 agent（尝试多种方式获取，优先 system init，回退预设列表）"""
    cmd = [
        "claude", "-p", "echo ready",
        "--dangerously-skip-permissions",
        "--output-format", "json",
        "--max-turns", "1",
    ]
    env = os.environ.copy()
    env.pop("CLAUDE_CODE_AUTO_COMPACT", None)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=str(PROJECT_DIR), env=env,
        )
    except subprocess.TimeoutExpired:
        print("❌ claude 命令超时（30秒）")
        sys.exit(1)

    events = _parse_claude_output(result.stdout)
    # 方式1: 从 system init 事件读取（流式 JSON 输出格式）
    init = next((e for e in events if isinstance(e, dict) and e.get("type") == "system" and e.get("subtype") == "init"), None)
    if init:
        agents = init.get("agents", [])
        if agents:
            print("可用 Agents:")
            for a in agents:
                print(f"  • {a}")
            return

    # 方式2: 回退到预设 agent 列表（当 output-format json 只返回 result 对象时）
    known_agents = [
        "Explore", "Plan", "general-purpose", "claude",
        "search-agent", "gen-video-qa", "gen-video-reviewer",
    ]
    print("可用 Agents（预设列表）:")
    for a in known_agents:
        print(f"  • {a}")


# ── 模式 2: 单 agent 执行 ────────────────────────────
def cmd_run(prompt: str, agent: Optional[str] = None, model: Optional[str] = None):
    """单 agent 执行，自动续接上次会话"""
    state = load_state()
    session_id = state.get("session_id")
    step = state.get("next_step", 1)

    if session_id and step > 1:
        print(f"🔄 续接会话 (step {step})")
    else:
        print(f"🚀 启动新任务")
        state = {"next_step": 1, "session_id": None, "history": []}

    print(f"📋 {prompt[:80]}...")
    if agent:
        print(f"🤖 Agent: {agent}")

    res = run_claude(prompt, session_id if step > 1 else None, agent=agent, model=model)

    if res.get("error"):
        print(f"❌ 失败: {res.get('stderr', '')[:300]}")
        sys.exit(1)

    state["session_id"] = res["session_id"]
    state["next_step"] = step + 1
    state.setdefault("history", []).append({
        "step": step, "agent": agent, "stop_reason": res["stop_reason"],
        "num_turns": res["num_turns"], "cost_usd": res["total_cost_usd"],
    })
    save_state(state)

    print(f"\n{'='*60}")
    print(f"✅ Step {step} | {res['stop_reason']} | {res['num_turns']} turns | ${res['total_cost_usd']:.4f}")
    if res.get('model'):
        print(f"🤖 Model: {res['model']}")
    print(f"{'='*60}")
    print(res["output"])


# ── 模式 3: 多 agent 流水线（顺序）───────────────────
def _print_step_result(step: int, res: dict):
    print(f"\n{'='*60}")
    print(f"✅ Step {step} | {res['stop_reason']} | {res['num_turns']} turns | ${res['total_cost_usd']:.4f}")
    print(f"{'='*60}")
    print(res["output"][:2000])


def cmd_pipeline(steps: list):
    """顺序执行多 agent 流水线"""
    # Pipeline 不继承 run/loop 等其他模式的状态，始终从 step 1 开始
    first = steps[0]
    total_steps = len(steps)
    print(f"🚀 流水线启动: Step 1/{total_steps}")

    # 写入初始进度
    write_progress({"mode": "pipeline", "status": "running", "total_steps": total_steps, "completed_steps": 0, "tasks": []})

    res = run_claude(first["prompt"], agent=first.get("agent"))
    if res.get("error"):
        print(f"❌ Step 1 失败: {res.get('stderr', '')[:300]}")
        clear_progress()
        sys.exit(1)
    session_id = res["session_id"]
    history = [{
        "step": 1, "agent": first.get("agent"),
        "stop_reason": res["stop_reason"], "num_turns": res["num_turns"],
        "cost_usd": res["total_cost_usd"], "output": res["output"][:500],
    }]
    state = {"session_id": session_id, "next_step": 2, "history": history}
    save_state(state)
    _print_step_result(1, res)

    # 更新进度
    write_progress({"mode": "pipeline", "status": "running", "total_steps": total_steps, "completed_steps": 1,
        "tasks": [{"step": 1, "status": "done", "turns": res["num_turns"], "cost_usd": res["total_cost_usd"]}]})

    remaining = steps[1:]

    for i, step_cfg in enumerate(remaining, start=2):
        print(f"\n🔄 Step {i}/{total_steps}...")
        res = run_claude(step_cfg["prompt"], session_id, agent=step_cfg.get("agent"))
        if res.get("error"):
            print(f"❌ Step {i} 失败: {res.get('stderr', '')[:300]}")
            clear_progress()
            sys.exit(1)

        session_id = res["session_id"]
        state["session_id"] = session_id
        state["next_step"] = i + 1
        history.append({
            "step": i, "agent": step_cfg.get("agent"),
            "stop_reason": res["stop_reason"], "num_turns": res["num_turns"],
            "cost_usd": res["total_cost_usd"], "output": res["output"][:500],
        })
        state["history"] = history
        save_state(state)
        _print_step_result(i, res)

        # 更新进度
        write_progress({"mode": "pipeline", "status": "running", "total_steps": total_steps, "completed_steps": i,
            "tasks": [{"step": h["step"], "status": "done", "turns": h["num_turns"], "cost_usd": h["cost_usd"]} for h in history]})

    total_cost = sum(h["cost_usd"] for h in history)
    total_turns = sum(h["num_turns"] for h in history)
    print(f"\n🎉 流水线完成！共 {len(history)} 步")
    print(f"   累计: {total_turns} 轮, ${total_cost:.4f}")
    write_progress({"mode": "pipeline", "status": "done", "total_steps": total_steps, "completed_steps": total_steps,
        "cost_usd": total_cost, "tasks": [{"step": h["step"], "status": "done", "turns": h["num_turns"], "cost_usd": h["cost_usd"]} for h in history]})
    clear_progress()


# ── 模式 4: 条件分支 ──────────────────────────────────
def evaluate_condition(condition: str, context: dict) -> bool:
    """简单条件评估（支持 >, <, >=, <=, ==, !=, 字符串包含）
    如果变量不在 context 中，尝试从 last_output 里用正则提取 key=value"""
    ctx = {**context, "output": context.get("last_output", "")}

    m = re.match(r"(\w+)\s*(>|<|>=|<=|==|!=)\s*(.+)", condition)
    if m:
        key, op, val_str = m.group(1), m.group(2), m.group(3).strip()
        if key not in ctx:
            output = ctx.get("output", "")
            extracted = None
            m2 = re.search(rf"{re.escape(key)}\s*[=：:]\s*(-?\d+(?:\.\d+)?)", output)
            if m2:
                extracted = m2.group(1)
                ctx[key] = float(extracted) if "." in extracted else int(extracted)
        if key not in ctx:
            print(f"⚠️ 条件变量 '{key}' 不在上下文中，默认 False")
            return False
        ctx_val = ctx[key]
        try:
            val = float(val_str) if "." in val_str else int(val_str)
        except ValueError:
            val = val_str.strip("\"'")
        ops = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
               ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
               "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
        return ops[op](ctx_val, val)

    if "contains" in condition:
        m2 = re.match(r"(\w+)\s+contains\s+(.+)", condition)
        if m2:
            key, substr = m2.group(1), m2.group(2).strip("\"'")
            return substr in ctx.get(key, "")
        if "output contains" in condition:
            substr = condition.split("output contains")[1].strip().strip("\"'")
            return substr in ctx.get("output", "")

    print(f"⚠️ 无法解析条件: {condition}")
    return False


def cmd_branch_pipeline(steps: list, condition: str, then_step_idx: int, else_step_idx: int):
    """带条件分支的流水线"""
    # Branch 不继承其他模式的状态，始终从头开始
    executed = set()
    total_steps = len(steps)

    # 执行第一个 step（通常是扫描/收集步骤）
    first = steps[0]
    print(f"🚀 分支流水线启动: Step 1/{total_steps}")
    res = run_claude(first["prompt"], agent=first.get("agent"))
    if res.get("error"):
        print(f"❌ Step 1 失败: {res.get('stderr', '')[:300]}")
        sys.exit(1)
    session_id = res["session_id"]
    context = {"last_output": res["output"], "last_turns": res["num_turns"]}
    _print_step_result(1, res)
    executed.add(0)

    # 第一个 step 执行完后立即评估条件
    cond_result = evaluate_condition(condition, context)
    print(f"\n🔀 条件评估: '{condition}' → {'TRUE' if cond_result else 'FALSE'}")

    # 根据条件决定执行路径
    target_idx = then_step_idx if cond_result else else_step_idx
    skip_idx = else_step_idx if cond_result else then_step_idx

    if skip_idx < total_steps:
        print(f"   → 跳过 Step {skip_idx + 1}，执行 Step {target_idx + 1}")

    # 执行条件选中的 step
    if target_idx < total_steps and target_idx != 0:
        step_cfg = steps[target_idx]
        current_step_num = target_idx + 1
        print(f"\n🔄 Step {current_step_num}/{total_steps}...")
        res = run_claude(step_cfg["prompt"], session_id, agent=step_cfg.get("agent"))
        if res.get("error"):
            print(f"❌ Step {current_step_num} 失败")
            sys.exit(1)

        session_id = res["session_id"]
        _print_step_result(current_step_num, res)

    print(f"\n🎉 分支流水线完成！")


# ── 模式 5: 并行派发 ──────────────────────────────────
def _run_in_worktree(task_cfg: dict, worktree_base: Optional[str] = None,
                     prefix: str = "orchestrator", max_output: int = 2000) -> dict:
    """在独立 worktree 中执行单个任务（parallel/fanout/genfilter/tournament 共用）
    注意：不再在 finally 里 merge，merge 由主线程的 _merge_and_cleanup 统一处理"""
    name = task_cfg.get("name", "unnamed")
    prompt = task_cfg["prompt"]
    agent = task_cfg.get("agent")
    model = task_cfg.get("model")
    use_worktree = task_cfg.get("worktree", True)

    worktree_path = None
    branch_name = f"{prefix}-{name}"
    res = None  # 预初始化，确保 finally 可访问
    try:
        if use_worktree and worktree_base:
            worktree_path = Path(worktree_base) / branch_name

            # 清理残留 worktree 和分支
            if worktree_path.exists():
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree_path)],
                    capture_output=True, text=True, timeout=15, cwd=str(PROJECT_DIR),
                )
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
            )

            worktree_path.mkdir(parents=True, exist_ok=True)
            rc = subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, str(worktree_path), "HEAD"],
                capture_output=True, text=True, timeout=30, cwd=str(PROJECT_DIR),
            )
            if rc.returncode == 0:
                print(f"  🌳 [{name}] worktree: {worktree_path}")
            else:
                print(f"  ⚠️ [{name}] worktree 创建失败，回退到共享目录: {rc.stderr[:100]}")
                worktree_path = None

        work_dir = str(worktree_path) if worktree_path else str(PROJECT_DIR)
        print(f"  🚀 [{name}] 启动... (dir: {Path(work_dir).name})")
        res = run_claude(prompt, agent=agent, model=model, cwd=work_dir)
        if res.get("error"):
            return {"name": name, "error": True, "stderr": res.get("stderr", "")[:300]}

        return {
            "name": name, "error": False,
            "session_id": res.get("session_id"),
            "output": res["output"][:max_output],
            "num_turns": res["num_turns"],
            "cost_usd": res["total_cost_usd"],
            "worktree": str(worktree_path) if worktree_path else None,
            "branch_name": branch_name,
        }
    finally:
        # 只清理失败任务的 worktree（成功任务的 merge 由主线程 _merge_and_cleanup 处理）
        if res is not None and res.get("error") and worktree_path and worktree_path.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                capture_output=True, text=True, timeout=15, cwd=str(PROJECT_DIR),
            )
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
            )
            print(f"  🧹 [{name}] 失败任务 worktree 已清理")


def _merge_and_cleanup(results: list, prefix: str, keep_all: bool = False) -> None:
    """在主线程中顺序合并所有成功任务的 worktree 分支并清理。
    必须在所有 future 完成后调用，避免 git index.lock 竞争。

    Args:
        results: _run_in_worktree 返回的结果列表
        prefix: 分支名前缀 ("orchestrator" 或 "fanout")
        keep_all: True 则跳过所有 merge 和 cleanup (--keep-worktree 模式)
    """
    if keep_all:
        for r in results:
            if r.get("worktree") and Path(r["worktree"]).exists():
                print(f"  📦 [{r['name']}] worktree 已保留: {r['worktree']}")
        return

    # 一次性检测 detached HEAD
    head_check = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "HEAD"],
        capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
    )
    is_detached = head_check.returncode != 0

    if is_detached:
        print("  ⚠️ detached HEAD 检测到，跳过所有合并")
        for r in results:
            if r.get("worktree") and not r.get("error") and Path(r["worktree"]).exists():
                print(f"  📦 [{r['name']}] worktree 保留 (detached HEAD): {r['worktree']}")
        return

    # 顺序合并每个成功任务的分支
    for r in results:
        if r.get("error") or not r.get("worktree") or not r.get("branch_name"):
            continue

        name = r["name"]
        branch_name = r["branch_name"]
        worktree_path = Path(r["worktree"])

        if not worktree_path.exists():
            continue

        merge_result = subprocess.run(
            ["git", "merge", "--no-edit", branch_name],
            capture_output=True, text=True, timeout=30, cwd=str(PROJECT_DIR),
        )

        if merge_result.returncode == 0:
            print(f"  🔗 [{name}] 已合并到当前分支")
            # 合并成功 → 清理 worktree 和分支
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path)],
                capture_output=True, text=True, timeout=15, cwd=str(PROJECT_DIR),
            )
            subprocess.run(
                ["git", "branch", "-d", branch_name],
                capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
            )
            print(f"  🧹 [{name}] worktree 已清理")
        else:
            print(f"  ⚠️ [{name}] 合并冲突，worktree 保留: {worktree_path}")
            print(f"     手动解决: cd {PROJECT_DIR} && git merge --no-edit {branch_name}")


def cmd_parallel(tasks: list):
    """并行执行多个任务"""
    print(f"🔄 并行执行 {len(tasks)} 个任务...")
    keep_all = any(t.get("keep_worktree", False) for t in tasks)

    # 写入初始进度
    task_names = [t.get("name", f"task_{i}") for i, t in enumerate(tasks)]
    write_progress({
        "mode": "parallel",
        "status": "running",
        "total_tasks": len(tasks),
        "completed_tasks": 0,
        "tasks": [{"name": n, "status": "running"} for n in task_names],
    })

    results = []
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, min(len(tasks), 8))) as executor:
        futures = {executor.submit(_run_in_worktree, t, str(WORKTREE_BASE), "orchestrator", 1000): t for t in tasks}
        for future in as_completed(futures):
            try:
                result = future.result(timeout=CLAUDE_TIMEOUT + 10)
                results.append(result)
            except Exception as ex:
                task = futures[future]
                results.append({
                    "name": task.get("name", "unnamed"),
                    "error": True,
                    "stderr": f"执行异常: {str(ex)[:200]}",
                })

            # 每个任务完成后更新进度
            completed_names = {r["name"] for r in results if not r.get("error")}
            running_names = [n for n in task_names if n not in completed_names and n not in {r["name"] for r in results if r.get("error")}]
            failed_names = {r["name"] for r in results if r.get("error")}
            write_progress({
                "mode": "parallel",
                "status": "running",
                "total_tasks": len(tasks),
                "completed_tasks": len(results),
                "tasks": [
                    {"name": n, "status": "done", "turns": next((r.get("num_turns", 0) for r in results if r["name"] == n), 0),
                     "cost_usd": next((r.get("cost_usd", 0) for r in results if r["name"] == n), 0)}
                    for n in completed_names
                ] + [
                    {"name": n, "status": "failed", "error": next((r.get("stderr", "")[:100] for r in results if r["name"] == n), "")}
                    for n in failed_names
                ] + [
                    {"name": n, "status": "running"} for n in running_names
                ],
            })

    # 主线程顺序合并 worktree 分支（避免 index.lock 竞争）
    _merge_and_cleanup(results, "orchestrator", keep_all=keep_all)

    print(f"\n{'='*60}")
    print("📊 并行结果:")
    for r in results:
        status = "✅" if not r.get("error") else "❌"
        print(f"  {status} [{r['name']}] {r.get('num_turns',0)} turns, ${r.get('cost_usd',0):.4f}")
        if not r.get("error"):
            print(f"    输出: {(r.get('output') or '')[:120]}")
        else:
            print(f"    错误: {r.get('stderr','')[:100]}")
    print(f"{'='*60}")

    # 完成后写入最终进度并清理
    total_cost = sum(r.get("cost_usd", 0) for r in results)
    write_progress({
        "mode": "parallel", "status": "done",
        "total_tasks": len(tasks), "completed_tasks": len(results),
        "cost_usd": total_cost,
        "tasks": [{"name": r["name"], "status": "done" if not r.get("error") else "failed",
                   "turns": r.get("num_turns", 0), "cost_usd": r.get("cost_usd", 0)} for r in results],
    })
    clear_progress()


# ── 交互式澄清（Superpowers brainstorming 风格） ───────
def _interactive_clarify(raw_prompt: str) -> str:
    """用 claude -p 生成澄清问题，收集用户回答，返回 refined prompt"""
    print("\n" + "=" * 60)
    print("🔍 Superpowers brainstorming: 需求澄清")
    print("=" * 60)

    clarify_prompt = f"""You are a senior engineer using Superpowers brainstorming methodology.

The user wants to run an automated workflow with this rough request:
"{raw_prompt}"

Before executing, generate 2-3 SHORT clarifying questions to understand:
1. The actual goal (what does "done" look like?)
2. Scope (which files/components are in/out?)
3. Constraints (TDD? code review? specific agent? worktree?)

Output ONLY the questions, one per line, prefixed with Q:. Keep them brief.
Do NOT execute anything. Just ask questions."""

    res = run_claude(clarify_prompt, max_turns=3, output_format="json")
    if res.get("error"):
        print(f"⚠️ 澄清阶段出错: {res.get('stderr', '')[:200]}")
        print("   继续使用原始 prompt...")
        return raw_prompt

    questions_text = res.get("output", "")
    questions = []
    for line in questions_text.splitlines():
        line = line.strip()
        if line.startswith("Q:") or line.startswith("Q："):
            questions.append(line.split(":", 1)[1].strip())

    if not questions:
        return raw_prompt

    print("\n请回答以下问题（直接输入答案，每行一个，或输入 skip 跳过）:\n")
    answers = []
    for i, q in enumerate(questions, 1):
        print(f"  Q{i}: {q}")
        ans = input(f"  A{i}: ").strip()
        if ans.lower() in ("skip", "跳过", "-"):
            answers.append(f"[skipped] {q}")
        else:
            answers.append(f"{q}: {ans}")

    refine_prompt = f"""原始任务: {raw_prompt}

澄清结果:
{chr(10).join(answers)}

Based on the above, generate a refined, actionable prompt for an automated workflow.
Output ONLY the refined prompt. No explanation."""

    res2 = run_claude(refine_prompt, max_turns=2, output_format="json")
    if res2.get("error") or not res2.get("output", "").strip():
        print("⚠️ refined prompt 生成失败，使用原始 prompt")
        return raw_prompt

    refined = res2["output"].strip()
    print(f"\n📝 Refined prompt:\n   {refined[:200]}...")
    return refined


# ── 模式 6: 长任务自动循环 ───────────────────────────
def cmd_loop(prompt: str, max_steps: int = MAX_STEPS, agent: Optional[str] = None, interactive: bool = False):
    """自动循环执行，每段做 prompt 中的一行任务，直到全部完成或达到 max_steps。
    支持断点续接：中断后重新运行会自动从上次停止的步骤继续。"""
    state = load_state()
    saved_steps = state.get("remaining_steps")
    saved_session = state.get("session_id")

    if interactive and not saved_steps:
        prompt = _interactive_clarify(prompt)

    history = state.get("history", [])

    all_steps = [line.strip() for line in prompt.splitlines() if line.strip()]
    if not all_steps:
        print("❌ prompt 为空，无任务可执行")
        return

    if saved_steps and saved_session:
        remaining = saved_steps
        session_id = saved_session
        print(f"🔄 从上次中断处继续，还剩 {len(remaining)} 步...")
    else:
        remaining = all_steps
        session_id = None
        history = []
        print(f"🚀 自动循环模式: 共 {len(remaining)} 步 (最多 {max_steps} 段)...")

    print(f"📋 总任务: {len(all_steps)} 步 | 本次最多执行: {max_steps} 段")
    if agent:
        print(f"🤖 Agent: {agent}")
    print(f"🔢 每段 {MAX_TURNS} 轮")
    print(f"{'='*60}")

    executed_count = len(all_steps) - len(remaining)

    # 写入初始进度
    write_progress({
        "mode": "loop",
        "status": "running",
        "total_steps": len(all_steps),
        "completed_steps": executed_count,
        "current_step": None,
        "cost_usd": sum(h.get("cost_usd", 0) for h in history),
        "tasks": [],
    })

    for i, step_prompt in enumerate(remaining[:max_steps]):
        current_step = executed_count + i + 1
        print(f"\n📌 Step {current_step} / {len(all_steps)}: {step_prompt[:60]}...")

        context_summary = ""
        if history:
            context_summary = "\n\n[之前步骤的摘要]\n"
            for h in history[-3:]:
                context_summary += f"- Step {h['step']}: {h.get('output_preview', '')[:100]}\n"
            context_summary += "\n[当前任务]\n"

        superpowers_injection = ""
        step_lower = step_prompt.lower()
        if any(kw in step_lower for kw in ["tdd", "test-driven", "测试驱动", "红绿重构"]):
            superpowers_injection = "\n\n[Superpowers: test-driven-development]\n" \
                "Red-Green-Refactor: write failing test first (RED), " \
                "watch it fail, then minimal code (GREEN), then refactor. " \
                "NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.\n"
        elif any(kw in step_lower for kw in ["plan", "规划", "拆解", "任务分解"]):
            superpowers_injection = "\n\n[Superpowers: writing-plans]\n" \
                "Break work into bite-sized tasks (2-5 min each). " \
                "Each task: exact file paths, complete code, verification steps. " \
                "Follow DRY, YAGNI, TDD. Save plan to docs/superpowers/plans/.\n"
        elif any(kw in step_lower for kw in ["subagent", "并行", "多 agent", "派发"]):
            superpowers_injection = "\n\n[Superpowers: subagent-driven-development]\n" \
                "Dispatch fresh subagent per task with two-stage review: " \
                "spec compliance first, then code quality. " \
                "Never inherit parent context. Isolate each subagent.\n"
        elif any(kw in step_lower for kw in ["review", "评审", "code review"]):
            superpowers_injection = "\n\n[Superpowers: requesting-code-review]\n" \
                "Review against plan/spec. Report issues by severity. " \
                "Critical issues block progress. Minor issues: note and proceed.\n"
        elif any(kw in step_lower for kw in ["debug", "调试", "修复 bug", "排查"]):
            superpowers_injection = "\n\n[Superpowers: systematic-debugging]\n" \
                "4-phase: understand before fixing, root cause trace, " \
                "defense-in-depth, condition-based waiting. " \
                "Don't patch symptoms. Verify fix before claiming done.\n"
        else:
            superpowers_injection = "\n\n[Superpowers workflow]\n" \
                "Before acting, invoke relevant skills (brainstorming, writing-plans, " \
                "test-driven-development, requesting-code-review). " \
                "Check skills before any response. No exceptions.\n"

        exec_prompt = context_summary + superpowers_injection + step_prompt
        res = run_claude(exec_prompt, session_id, agent=agent)

        if res.get("error"):
            print(f"❌ Step {current_step} 失败: {res.get('stderr', '')[:300]}")
            save_state({
                "session_id": session_id,
                "remaining_steps": remaining[i:],
                "history": history,
                "next_step": current_step,
            })
            sys.exit(1)

        session_id = res["session_id"]
        history.append({
            "step": current_step,
            "agent": agent,
            "stop_reason": res["stop_reason"],
            "num_turns": res["num_turns"],
            "cost_usd": res["total_cost_usd"],
            "output_preview": res["output"][:200],
        })

        print(f"{'='*60}")
        print(f"✅ Step {current_step} | {res['stop_reason']} | {res['num_turns']} turns | ${res['total_cost_usd']:.4f}")
        print(f"{'='*60}")
        print(res["output"][:1500])

        # 写入进度
        total_cost_so_far = sum(h["cost_usd"] for h in history)
        write_progress({
            "mode": "loop",
            "status": "running",
            "total_steps": len(all_steps),
            "completed_steps": current_step,
            "current_step": current_step,
            "current_step_preview": step_prompt[:80],
            "cost_usd": total_cost_so_far,
            "tasks": [{
                "step": h["step"],
                "status": "done",
                "turns": h["num_turns"],
                "cost_usd": h["cost_usd"],
            } for h in history],
        })

        remaining_after = remaining[i + 1:]
        if not remaining_after:
            total_cost = sum(h["cost_usd"] for h in history)
            total_turns = sum(h["num_turns"] for h in history)
            print(f"\n🎉 全部 {len(all_steps)} 步完成！累计 {total_turns} 轮, ${total_cost:.4f}")
            write_progress({
                "mode": "loop", "status": "done",
                "total_steps": len(all_steps), "completed_steps": len(all_steps),
                "cost_usd": total_cost,
                "tasks": [{"step": h["step"], "status": "done", "turns": h["num_turns"], "cost_usd": h["cost_usd"]} for h in history],
            })
            clear_progress()
            return

        save_state({
            "session_id": session_id,
            "remaining_steps": remaining_after,
            "history": history,
            "next_step": current_step + 1,
        })

    remaining_final = remaining[max_steps:]
    if remaining_final:
        total_cost = sum(h["cost_usd"] for h in history)
        total_turns = sum(h["num_turns"] for h in history)
        print(f"\n⏸️  本次执行 {max_steps} 段完成，还剩 {len(remaining_final)} 步未执行")
        print(f"   累计: {total_turns} 轮, ${total_cost:.4f}")
        print(f"   再次运行即可继续: python3 workflow.py loop \"<原prompt>\" --max-steps {max_steps}")


# ── 模式 6 补充: 查看会话 ────────────────────────────
def cmd_sessions():
    """查看当前活跃的 claude 会话"""
    result = subprocess.run(
        ["claude", "agents", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        print(f"❌ 获取会话列表失败: {result.stderr[:300]}")
        sys.exit(1)

    try:
        sessions = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        print(f"❌ 无法解析会话列表输出")
        print(f"   stdout: {result.stdout[:300]}")
        sessions = []
    if not sessions:
        print("📭 没有活跃的后台会话")
        return

    print(f"📊 活跃会话 ({len(sessions)}):")
    for s in sessions:
        sid = s.get("sessionId", "?")[:12]
        status = s.get("status", "?")
        cwd = s.get("cwd", "?")
        print(f"  • {sid}... | {status} | {cwd}")

    state = load_state()
    if state.get("session_id"):
        sid = state["session_id"][:12]
        step = state.get("next_step", 1)
        hist = state.get("history", [])
        total_cost = sum(h.get("cost_usd", 0) for h in hist)
        print(f"\n📌 当前编排状态:")
        print(f"   Session: {sid}...")
        print(f"   Step: {step}")
        print(f"   已执行: {len(hist)} 步")
        print(f"   累计: ${total_cost:.4f}")


# ── 进度查询 ──────────────────────────────────────────
def cmd_progress():
    """读取进度文件并格式化输出，供 Claude Code 轮询使用"""
    if not PROGRESS_FILE.exists():
        print("📭 没有正在执行的工作流任务")
        return

    try:
        with open(PROGRESS_FILE, "r") as f:
            progress = json.load(f)
    except (json.JSONDecodeError, ValueError):
        print("⚠️ 进度文件损坏")
        return

    mode = progress.get("mode", "unknown")
    status = progress.get("status", "unknown")
    updated = progress.get("updated_at", "?")
    tasks = progress.get("tasks", [])

    if status == "done":
        cost = progress.get("cost_usd", 0)
        print(f"✅ {mode} 已完成 | 💰 ${cost:.4f} | 更新于 {updated}")
        for t in tasks:
            name = t.get("name", t.get("step", t.get("iter", "?")))
            t_status = t.get("status", "?")
            turns = t.get("turns", "")
            t_cost = t.get("cost_usd", "")
            print(f"  • [{name}] {t_status}" + (f" | {turns} turns" if turns else "") + (f" | ${t_cost:.4f}" if t_cost else ""))
        return

    # running
    print(f"🔄 {mode} 执行中 | 更新于 {updated}")

    if mode == "loop":
        total = progress.get("total_steps", "?")
        completed = progress.get("completed_steps", 0)
        current = progress.get("current_step")
        cost = progress.get("cost_usd", 0)
        preview = progress.get("current_step_preview", "")
        print(f"   进度: {completed}/{total} 步 | 💰 ${cost:.4f}")
        if current:
            print(f"   当前: Step {current} — {preview}")
        for t in tasks:
            print(f"  ✅ Step {t['step']} | {t['turns']} turns | ${t['cost_usd']:.4f}")

    elif mode == "parallel":
        total = progress.get("total_tasks", "?")
        completed = progress.get("completed_tasks", 0)
        print(f"   进度: {completed}/{total} 任务")
        for t in tasks:
            t_status = t.get("status", "?")
            icon = "✅" if t_status == "done" else "❌" if t_status == "failed" else "🔄"
            name = t["name"]
            turns = t.get("turns", "")
            t_cost = t.get("cost_usd", "")
            print(f"  {icon} [{name}]" + (f" {turns} turns, ${t_cost:.4f}" if turns else ""))

    elif mode == "pipeline":
        total = progress.get("total_steps", "?")
        completed = progress.get("completed_steps", 0)
        print(f"   进度: {completed}/{total} 步")
        for t in tasks:
            print(f"  ✅ Step {t['step']} | {t['turns']} turns | ${t['cost_usd']:.4f}")

    elif mode == "verify":
        phase = progress.get("phase", "?")
        current_round = progress.get("current_round", 0)
        max_rounds = progress.get("max_rounds", "?")
        print(f"   阶段: {phase} | 轮次: {current_round}/{max_rounds}")

    elif mode == "loop_until":
        current_iter = progress.get("current_iteration", 0)
        max_iter = progress.get("max_iterations", "?")
        cost = progress.get("cost_usd", 0)
        print(f"   轮次: {current_iter}/{max_iter} | 💰 ${cost:.4f}")
        for t in tasks:
            print(f"  • 轮次 {t['iter']}: {t.get('outcome', '')[:60]}")

    else:
        print(f"   {json.dumps(progress, ensure_ascii=False)[:200]}")


# ── 入口 ──────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 workflow.py agents                          # 查看 agent")
        print("  python3 workflow.py run \"任务\" [--agent X] [--model Y]")
        print("  python3 workflow.py sessions                        # 查看会话")
        print()
        print("  流水线 (pipeline):")
        print('  python3 workflow.py pipeline \\')
        print('    --step "探索:列出 .py 文件" --agent Explore \\')
        print('    --step "分析:评估复杂度" --agent general-purpose \\')
        print('    --step "规划:给出方案" --agent Plan')
        print()
        print("  条件分支 (branch):")
        print('  python3 workflow.py branch \\')
        print('    --step "扫描:统计高危问题数" --agent Explore \\')
        print('    --step "报告" --agent general-purpose \\')
        print('    --step "修复" --agent general-purpose \\')
        print('    --step "跳过" --agent general-purpose \\')
        print('    --if "bugs_found > 0" --then-step 3 --else-step 4')
        print()
        print("  并行 (parallel):")
        print('  python3 workflow.py parallel \\')
        print('    --task "分析 a.py" --agent Explore --name a \\')
        print('    --task "分析 b.py" --agent Explore --name b')
        print()
        print("  长任务 (loop):")
        print('  python3 workflow.py loop "重构代码库" --max-steps 100')
        print()
        print("  Classify-and-act:")
        print("  python3 workflow.py classify \"Classify this bug\" \\")
        print("    --class-security \"Run security audit...\" \\")
        print("    --class-performance \"Run perf analysis...\" \\")
        print("    --default \"Run general analysis...\"")
        print()
        print("  Fan-out-and-synthesize:")
        print("  python3 workflow.py fanout \"Analyze all files\" \\")
        print("    --subtask \"Check auth.py\" --subtask \"Check api.py\" \\")
        print("    --synthesize \"Combine findings into report\"")
        print()
        print("  Adversarial verification:")
        print("  python3 workflow.py verify \"Implement feature X\" \\")
        print("    --rubric \"Must have tests, handle errors, follow style guide\"")
        print()
        print("  Generate-and-filter:")
        print("  python3 workflow.py genfilter \"Generate 5 CLI names\" \\")
        print("    --count 5 --rubric \"Short, memorable\" --filter-top 3")
        print()
        print("  Tournament:")
        print("  python3 workflow.py tournament \"Implement LRU cache\" \\")
        print("    --contestants 3 --judge \"Best: correct, fast, readable\"")
        print()
        print("  Loop until done:")
        print("  python3 workflow.py loop_until \"Fix all failing tests\" \\")
        print("    --stop-condition \"All pytest tests pass\" --max-iterations 10")
        sys.exit(1)

    action = sys.argv[1]
    remaining = sys.argv[2:]

    if action == "agents":
        cmd_agents()
    elif action == "run":
        prompt, agent, model = _parse_run_args(remaining)
        cmd_run(prompt, agent=agent, model=model)
    elif action == "pipeline":
        steps, _ = _parse_pipeline_args(remaining)
        cmd_pipeline(steps)
    elif action == "branch":
        steps, branch = _parse_pipeline_args(remaining)
        cmd_branch_pipeline(
            steps,
            condition=branch.get("condition", ""),
            then_step_idx=branch.get("then", 1) - 1,
            else_step_idx=branch.get("else", len(steps)) - 1,
        )
    elif action == "parallel":
        tasks = _parse_parallel_args(remaining)
        cmd_parallel(tasks)
    elif action == "loop":
        prompt, max_steps, agent, interactive = _parse_loop_args(remaining)
        cmd_loop(prompt, max_steps=max_steps, agent=agent, interactive=interactive)
    elif action == "sessions":
        cmd_sessions()
    elif action == "progress":
        cmd_progress()
    elif action == "classify":
        classify_prompt, actions, default_action = _parse_classify_args(remaining)
        cmd_classify(classify_prompt, actions, default_action)
    elif action == "fanout":
        main_prompt, subtasks, synth_prompt, agent = _parse_fanout_args(remaining)
        cmd_fanout(main_prompt, subtasks, synth_prompt, agent)
    elif action == "verify":
        task_prompt, rubric, verifier_agent, max_rounds = _parse_verify_args(remaining)
        cmd_verify(task_prompt, rubric, verifier_agent, max_rounds)
    elif action == "genfilter":
        gen_prompt, count, rubric, filter_prompt, filter_top, agent = _parse_genfilter_args(remaining)
        cmd_genfilter(gen_prompt, count, rubric, filter_prompt, filter_top, agent)
    elif action == "tournament":
        task_prompt, contestants, judge_prompt, agent, model = _parse_tournament_args(remaining)
        cmd_tournament(task_prompt, contestants, judge_prompt, agent, model)
    elif action == "loop_until":
        task_prompt, stop_condition, max_iterations, agent = _parse_loop_until_args(remaining)
        cmd_loop_until(task_prompt, stop_condition, max_iterations, agent)
    else:
        print(f"❌ 未知命令: {action}")
        print("支持: agents, run, pipeline, branch, parallel, loop, sessions,")
        print("       classify, fanout, verify, genfilter, tournament, loop_until")
        sys.exit(1)


# ── 参数解析 ──────────────────────────────────────────
def _parse_run_args(args: list) -> tuple:
    prompt = ""
    agent = None
    model = None
    i = 0
    while i < len(args):
        if args[i] == "--agent" and i + 1 < len(args):
            agent = args[i + 1]
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and not prompt:
            prompt = args[i]
            i += 1
        else:
            i += 1
    return prompt, agent, model


def _parse_pipeline_args(args: list) -> tuple:
    steps = []
    current_step = {}
    i = 0
    while i < len(args):
        if args[i] == "--step" and i + 1 < len(args):
            if current_step:
                steps.append(current_step)
            current_step = {"prompt": args[i + 1]}
            i += 2
        elif args[i] == "--agent" and i + 1 < len(args):
            current_step["agent"] = args[i + 1]
            i += 2
        elif args[i] == "--if" and i + 1 < len(args):
            current_step["condition"] = args[i + 1]
            i += 2
        elif args[i] == "--then-step" and i + 1 < len(args):
            current_step["then"] = _safe_int(args[i + 1], "--then-step")
            i += 2
        elif args[i] == "--else-step" and i + 1 < len(args):
            current_step["else"] = _safe_int(args[i + 1], "--else-step")
            i += 2
        else:
            i += 1
    if current_step:
        steps.append(current_step)

    branch = {}
    for s in steps:
        if "condition" in s:
            branch = {
                "condition": s.pop("condition"),
                "then": s.pop("then", 1),
                "else": s.pop("else", len(steps)),
            }
            break
    return steps, branch


def _parse_parallel_args(args: list) -> list:
    tasks = []
    current = {}
    i = 0
    while i < len(args):
        if args[i] == "--task" and i + 1 < len(args):
            if current:
                tasks.append(current)
            current = {"prompt": args[i + 1]}
            i += 2
        elif args[i] == "--agent" and i + 1 < len(args):
            current["agent"] = args[i + 1]
            i += 2
        elif args[i] == "--name" and i + 1 < len(args):
            current["name"] = args[i + 1]
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            current["model"] = args[i + 1]
            i += 2
        elif args[i] == "--no-worktree":
            current["worktree"] = False
            i += 1
        elif args[i] == "--keep-worktree":
            current["keep_worktree"] = True
            i += 1
        else:
            i += 1
    if current:
        tasks.append(current)
    return tasks


def _parse_loop_args(args: list) -> tuple:
    prompt = ""
    max_steps = MAX_STEPS
    agent = None
    interactive = False
    i = 0
    while i < len(args):
        if args[i] == "--max-steps" and i + 1 < len(args):
            max_steps = _safe_int(args[i + 1], "--max-steps", MAX_STEPS)
            i += 2
        elif args[i] == "--agent" and i + 1 < len(args):
            agent = args[i + 1]
            i += 2
        elif args[i] == "--interactive":
            interactive = True
            i += 1
        elif not args[i].startswith("--") and not prompt:
            prompt = args[i]
            i += 1
        else:
            i += 1
    return prompt, max_steps, agent, interactive




# ╔══════════════════════════════════════════════════════════════╗
# ║  6 种官方 Workflow Pattern 实现                              ║
# ║  Reference: https://claude.com/blog/a-harness-for-every-task ║
# ╚══════════════════════════════════════════════════════════════╝

# ── Pattern 1: Classify-and-act ───────────────────────────────
def cmd_classify(classify_prompt: str, actions: dict, default_action: str = ""):
    """
    先用 classifier agent 对任务分类，再根据分类结果路由到不同 action。
    actions: {"security": "prompt for security path", "performance": "...", ...}
    """
    print("🔍 Classify-and-act: 分类阶段...")
    res = run_claude(classify_prompt, agent="Explore", max_turns=6)
    if res.get("error"):
        print(f"❌ 分类失败: {res.get('stderr', '')[:300]}")
        sys.exit(1)

    classification = res["output"].strip().lower()
    print(f"   分类结果: {classification[:100]}")

    # 匹配分类到 action key
    matched_key = None
    for key in actions:
        if key.lower() in classification:
            matched_key = key
            break

    if matched_key:
        action_prompt = actions[matched_key]
        print(f"   → 路由到 [{matched_key}]")
    elif default_action:
        action_prompt = default_action
        print(f"   → 使用默认 action")
    else:
        print("❌ 无法匹配分类，且未提供默认 action")
        sys.exit(1)

    print(f"\n🔄 执行 action...")
    act_res = run_claude(action_prompt, agent="general-purpose", max_turns=6)
    if act_res.get("error"):
        # 如果 action 超时或失败，尝试降级到 Explore agent
        print(f"⚠️ Action 执行失败，降级到 Explore agent 重试...")
        act_res = run_claude(action_prompt, agent="Explore", max_turns=6)
        if act_res.get("error"):
            print(f"❌ Action 执行失败: {act_res.get('stderr', '')[:300]}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"✅ Classify-and-act 完成")
    print(f"{'='*60}")
    print(act_res["output"])


# ── Pattern 2: Fan-out-and-synthesize ──────────────────────────

def cmd_fanout(main_prompt: str, subtasks: list, synthesize_prompt: str = "", agent: Optional[str] = None):
    """
    Fan-out-and-synthesize: 并发执行子任务，然后汇总结果。
    subtasks: list of {"prompt": str, "name": str, "agent": str}
    """
    print(f"🔄 Fan-out-and-synthesize: {len(subtasks)} 个子任务...")
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)

    # Fan-out 阶段
    fanout_results = []
    with ThreadPoolExecutor(max_workers=max(1, min(len(subtasks), 8))) as executor:
        futures = {
            executor.submit(_run_in_worktree, t, str(WORKTREE_BASE), "fanout", 2000): t
            for t in subtasks
        }
        for future in as_completed(futures):
            try:
                result = future.result(timeout=CLAUDE_TIMEOUT + 10)
                fanout_results.append(result)
            except Exception as ex:
                task = futures[future]
                fanout_results.append({
                    "name": task.get("name", "unnamed"),
                    "error": True, "stderr": f"执行异常: {str(ex)[:200]}",
                })

    # 主线程顺序合并 worktree 分支
    _merge_and_cleanup(fanout_results, "fanout")

    # 构建汇总上下文
    context_parts = ["[Fan-out 结果汇总]\n"]
    for r in fanout_results:
        status = "✅" if not r.get("error") else "❌"
        context_parts.append(f"\n{status} [{r['name']}]:")
        if r.get("error"):
            context_parts.append(f"  错误: {r.get('stderr', '')[:200]}")
        else:
            context_parts.append(r.get("output", "")[:1500])

    fanout_context = "\n".join(context_parts)

    # Synthesize 阶段
    if synthesize_prompt:
        print(f"\n🔄 汇总阶段...")
        full_synth_prompt = f"{synthesize_prompt}\n\n{fanout_context}"
        synth_res = run_claude(full_synth_prompt, agent=agent or "general-purpose", max_turns=12)
        if synth_res.get("error"):
            print(f"❌ 汇总失败: {synth_res.get('stderr', '')[:300]}")
            # 仍然返回 fanout 结果
            print(f"\n{'='*60}")
            print("📊 Fan-out 结果（汇总失败）:")
            for r in fanout_results:
                status = "✅" if not r.get("error") else "❌"
                print(f"  {status} [{r['name']}]")
            print(f"{'='*60}")
            return

        print(f"\n{'='*60}")
        print(f"✅ Fan-out-and-synthesize 完成")
        print(f"   子任务: {len(fanout_results)} 个")
        print(f"{'='*60}")
        print(synth_res["output"])
    else:
        print(f"\n{'='*60}")
        print(f"✅ Fan-out 完成（无汇总步骤）")
        print(f"   子任务: {len(fanout_results)} 个")
        print(f"{'='*60}")
        for r in fanout_results:
            status = "✅" if not r.get("error") else "❌"
            print(f"\n{status} [{r['name']}]:")
            if r.get("error"):
                print(f"  错误: {r.get('stderr', '')[:200]}")
            else:
                print(r.get("output", "")[:1000])


# ── Pattern 3: Adversarial verification ────────────────────────
def cmd_verify(task_prompt: str, rubric: str, verifier_agent: str = "Explore", max_rounds: int = 2):
    """
    Adversarial verification: 执行任务，然后用 verifier 对结果进行对抗式验证。
    可选的 max_rounds: 最多迭代修复轮数。
    """
    print("🔍 Adversarial verification: 主任务阶段...")

    # 写入初始进度
    write_progress({"mode": "verify", "status": "running", "phase": "executing", "max_rounds": max_rounds, "current_round": 0, "tasks": []})

    main_res = run_claude(task_prompt, agent="general-purpose", max_turns=12)
    if main_res.get("error"):
        print(f"❌ 主任务失败: {main_res.get('stderr', '')[:300]}")
        clear_progress()
        sys.exit(1)

    current_output = main_res["output"]
    print(f"   主任务完成: {main_res['num_turns']} turns")

    for round_num in range(max_rounds):
        print(f"\n🔍 验证轮次 {round_num + 1}/{max_rounds}...")

        # 更新进度
        write_progress({"mode": "verify", "status": "running", "phase": "verifying",
            "max_rounds": max_rounds, "current_round": round_num + 1,
            "tasks": [{"round": round_num + 1, "phase": "verifying"}]})

        verify_prompt = f"""[Verification Rubric]
{rubric}

[Task Output to Verify]
{current_output}

Evaluate the output against the rubric. Output ONLY:
- PASS or FAIL
- List of issues found (or "None" if PASS)
- Severity of each issue: critical / minor"""

        verify_res = run_claude(verify_prompt, agent=verifier_agent, max_turns=6)
        if verify_res.get("error"):
            print(f"❌ 验证失败: {verify_res.get('stderr', '')[:300]}")
            break

        verdict_text = verify_res["output"].strip()
        # 去掉 markdown 格式（**PASS** → PASS）再检测
        verdict_clean = re.sub(r'[*_`#]', '', verdict_text).strip()
        print(f"   验证结果: {verdict_text[:200]}")

        if verdict_clean.upper().startswith("PASS"):
            print(f"\n✅ 验证通过！")
            break

        # FAIL - 修复轮次
        if round_num < max_rounds - 1:
            print(f"   🔧 修复轮次...")
            fix_prompt = f"""[Original Task]
{task_prompt}

[Previous Output (has issues)]
{current_output}

[Verification Issues]
{verdict_text}

Fix the issues above and produce corrected output."""
            fix_res = run_claude(fix_prompt, agent="general-purpose", max_turns=12)
            if fix_res.get("error"):
                print(f"❌ 修复失败: {fix_res.get('stderr', '')[:300]}")
                break
            current_output = fix_res["output"]
            print(f"   修复完成: {fix_res['num_turns']} turns")
        else:
            print(f"\n⚠️ 达到最大轮数，验证仍未通过")

    print(f"\n{'='*60}")
    print(f"✅ Adversarial verification 完成")
    print(f"{'='*60}")
    print(current_output)
    clear_progress()


# ── Pattern 4: Generate-and-filter ─────────────────────────────
def cmd_genfilter(generation_prompt: str, count: int = 3, rubric: str = "",
                  filter_prompt: str = "", filter_top: int = 1, agent: Optional[str] = None):
    """
    Generate-and-filter: 生成 N 个方案，然后用 rubric 筛选出最好的 K 个。
    """
    print(f"🔄 Generate-and-filter: 生成 {count} 个方案...")

    # 生成阶段
    generation_tasks = []
    for i in range(count):
        task_prompt = f"""[Generation Task #{i+1}/{count}]
{generation_prompt}

Produce a complete, independent solution. Be creative and thorough."""
        generation_tasks.append({
            "prompt": task_prompt,
            "name": f"gen-{i+1}",
            "agent": agent or "general-purpose",
            "worktree": True,
        })

    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)
    gen_results = []
    with ThreadPoolExecutor(max_workers=max(1, min(count, 8))) as executor:
        futures = {
            executor.submit(_run_in_worktree, t, str(WORKTREE_BASE), "fanout", 2000): t
            for t in generation_tasks
        }
        for future in as_completed(futures):
            try:
                result = future.result(timeout=CLAUDE_TIMEOUT + 10)
                gen_results.append(result)
            except Exception as ex:
                task = futures[future]
                gen_results.append({
                    "name": task.get("name", "unnamed"),
                    "error": True, "stderr": f"异常: {str(ex)[:200]}",
                })

    # 主线程顺序合并 worktree 分支
    _merge_and_cleanup(gen_results, "fanout")

    successful_gens = [r for r in gen_results if not r.get("error")]
    if not successful_gens:
        print("❌ 所有生成任务均失败")
        sys.exit(1)

    print(f"\n🔍 筛选阶段: 使用 rubric 筛选 top {filter_top}...")

    # 构建筛选上下文
    gen_context_parts = [f"[Generated {len(successful_gens)} Solutions]\n"]
    for r in successful_gens:
        gen_context_parts.append(f"\n--- {r['name']} ---\n{r.get('output', '')[:2000]}")
    gen_context = "\n".join(gen_context_parts)

    if not filter_prompt:
        filter_prompt = f"""[Rubric for Evaluation]
{rubric}

Evaluate each solution against the rubric. Score each 1-10 on:
1. Correctness / Completeness
2. Quality / Robustness
3. Alignment with rubric criteria

Output ONLY a JSON array ranked by score (best first):
[
  {{"rank": 1, "name": "...", "score": 9, "reason": "..."}},
  ...
]"""

    full_filter_prompt = f"{filter_prompt}\n\n{gen_context}"
    filter_res = run_claude(full_filter_prompt, agent="Explore", max_turns=10)
    if filter_res.get("error"):
        print(f"❌ 筛选失败: {filter_res.get('stderr', '')[:300]}")
        # 回退：返回所有成功生成的结果
        print(f"\n{'='*60}")
        print("📊 生成结果（筛选失败，返回全部）:")
        for r in successful_gens:
            print(f"\n--- {r['name']} ---\n{r.get('output', '')[:500]}")
        print(f"{'='*60}")
        return

    print(f"\n{'='*60}")
    print(f"✅ Generate-and-filter 完成")
    print(f"   生成: {len(successful_gens)} 个 | 筛选 Top {filter_top}")
    print(f"{'='*60}")
    print(filter_res["output"])

    # 同时展示 top 结果的完整内容
    print(f"\n{'='*60}")
    print(f"📋 Top {filter_top} 方案详情:")
    print(f"{'='*60}")
    # 简单解析：在 filter output 里找排名靠前的 name
    top_names = []
    for r in successful_gens:
        if r["name"] in filter_res["output"]:
            top_names.append(r["name"])
    # 如果解析失败，默认取前 filter_top 个
    if not top_names and len(successful_gens) >= filter_top:
        top_names = [successful_gens[i]["name"] for i in range(min(filter_top, len(successful_gens)))]

    for r in successful_gens:
        if r["name"] in top_names:
            print(f"\n--- {r['name']} ---\n{r.get('output', '')[:2000]}")


# ── Pattern 5: Tournament ──────────────────────────────────────
def cmd_tournament(task_prompt: str, contestants: int = 3,
                   judge_prompt: str = "", agent: Optional[str] = None,
                   model: Optional[str] = None):
    """
    Tournament: N 个 agent 竞争同一任务，judge agent  pairwise 评比选出赢家。
    """
    print(f"🏆 Tournament: {contestants} 个参赛者...")

    # Contestants 阶段
    contest_tasks = []
    approaches = [
        "Approach A: Use a simple, direct implementation with minimal dependencies.",
        "Approach B: Use a robust, production-grade implementation with full error handling.",
        "Approach C: Use an optimized implementation prioritizing performance.",
        "Approach D: Use a creative, unconventional approach that might have unique advantages.",
        "Approach E: Use a well-tested, standard library-only approach.",
    ]
    for i in range(contestants):
        approach = approaches[i % len(approaches)]
        task_prompt_i = f"""[Tournament Entry #{i+1}/{contestants}]
{approach}

[Task]
{task_prompt}

Produce your best complete solution following your approach. Be thorough."""
        contest_tasks.append({
            "prompt": task_prompt_i,
            "name": f"contestant-{i+1}",
            "agent": agent or "general-purpose",
            "model": model,
            "worktree": True,
        })

    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)
    contest_results = []
    with ThreadPoolExecutor(max_workers=max(1, min(contestants, 8))) as executor:
        futures = {
            executor.submit(_run_in_worktree, t, str(WORKTREE_BASE), "fanout", 2000): t
            for t in contest_tasks
        }
        for future in as_completed(futures):
            try:
                result = future.result(timeout=CLAUDE_TIMEOUT + 10)
                contest_results.append(result)
            except Exception as ex:
                task = futures[future]
                contest_results.append({
                    "name": task.get("name", "unnamed"),
                    "error": True, "stderr": f"异常: {str(ex)[:200]}",
                })

    # 主线程顺序合并 worktree 分支
    _merge_and_cleanup(contest_results, "fanout")

    successful = [r for r in contest_results if not r.get("error")]
    if len(successful) < 2:
        print(f"❌ 需要至少 2 个成功参赛者，实际: {len(successful)}")
        if successful:
            print(f"\n{'='*60}")
            print(f"🏆 唯一获胜者: {successful[0]['name']}")
            print(f"{'='*60}")
            print(successful[0].get("output", "")[:2000])
        sys.exit(1)

    # Judge 阶段
    print(f"\n⚖️ Judge 阶段: 评比 {len(successful)} 个方案...")

    contest_context_parts = [f"[Tournament Task]\n{task_prompt}\n\n[Contestant Submissions]\n"]
    for r in successful:
        contest_context_parts.append(f"\n--- {r['name']} ---\n{r.get('output', '')[:2000]}")
    contest_context = "\n".join(contest_context_parts)

    if not judge_prompt:
        judge_prompt = """You are an expert judge. Evaluate each contestant submission against the task requirements.

For each submission, score 1-10 on:
1. Correctness (does it solve the task?)
2. Code quality (readability, structure)
3. Robustness (error handling, edge cases)
4. Efficiency (performance considerations)

Output a JSON array ranked by overall score:
[
  {"rank": 1, "name": "contestant-1", "score": 8.5, "reason": "..."},
  ...
]

Be critical but fair. The winner should have a clear advantage."""

    full_judge_prompt = f"{judge_prompt}\n\n{contest_context}"
    judge_res = run_claude(full_judge_prompt, agent="Explore", max_turns=10)
    if judge_res.get("error"):
        print(f"❌ Judge 失败: {judge_res.get('stderr', '')[:300]}")
        print(f"\n{'='*60}")
        print("📊 参赛结果（Judge 失败）:")
        for r in successful:
            print(f"\n--- {r['name']} ---\n{r.get('output', '')[:500]}")
        print(f"{'='*60}")
        return

    print(f"\n{'='*60}")
    print(f"🏆 Tournament 完成")
    print(f"   参赛者: {len(successful)} 个")
    print(f"{'='*60}")
    print(judge_res["output"])

    # 展示获胜者详情
    print(f"\n{'='*60}")
    print(f"🥇 获胜方案详情:")
    print(f"{'='*60}")
    # 优先从 judge 输出解析 JSON 数组；失败则回退到启发式
    winner_name = None
    try:
        json_match = re.search(r'\[\s*\{.*"rank".*\}\s*\]', judge_res["output"], re.DOTALL)
        if json_match:
            ranking = json.loads(json_match.group(0))
            if ranking and isinstance(ranking, list):
                top_entry = ranking[0]
                winner_name = top_entry.get("name") or top_entry.get("contestant")
                if winner_name:
                    print(f"   (JSON 解析: 排名第1 = {winner_name})")
    except Exception:
        pass
    if not winner_name:
        # 回退：judge output 中先出现的参赛者名字更可能是赢家
        for r in successful:
            if r["name"] in judge_res["output"]:
                if winner_name is None or judge_res["output"].index(r["name"]) < judge_res["output"].index(winner_name):
                    winner_name = r["name"]
        if not winner_name:
            winner_name = successful[0]["name"]
    for r in successful:
        if r["name"] == winner_name:
            print(f"\n--- {r['name']} ---\n{r.get('output', '')[:3000]}")
            break


# ── Pattern 6: Loop until done ─────────────────────────────────
def cmd_loop_until(task_prompt: str, stop_condition: str, max_iterations: int = 10,
                   agent: Optional[str] = None):
    """
    Loop until done: 循环执行任务，每次检查停止条件，满足则退出。
    stop_condition: 描述停止条件的文本（Claude 每次执行后评估是否满足）。
    """
    print(f"🔁 Loop until done: 最多 {max_iterations} 轮")
    print(f"   停止条件: {stop_condition[:80]}...")

    state = load_state()
    saved_iter = state.get("loop_until_iter", 0)
    saved_session = state.get("session_id")
    saved_history = state.get("loop_until_history", [])

    if saved_iter > 0 and saved_session:
        print(f"🔄 从第 {saved_iter + 1} 轮继续...")
        start_iter = saved_iter
    else:
        start_iter = 0
        saved_history = []

    # 写入初始进度
    write_progress({"mode": "loop_until", "status": "running", "max_iterations": max_iterations,
        "current_iteration": start_iter, "stop_condition": stop_condition[:80], "tasks": []})

    session_id = saved_session
    iteration = start_iter

    while iteration < max_iterations:
        iteration += 1
        print(f"\n📌 轮次 {iteration}/{max_iterations}...")

        context_summary = ""
        if saved_history:
            context_summary = "\n\n[之前轮次摘要]\n"
            for h in saved_history[-2:]:
                context_summary += f"- 轮次 {h['iter']}: {h.get('outcome', '')[:120]}\n"
            context_summary += "\n[当前任务]\n"

        exec_prompt = f"{context_summary}{task_prompt}"
        res = run_claude(exec_prompt, session_id, agent=agent)

        if res.get("error"):
            print(f"❌ 轮次 {iteration} 失败: {res.get('stderr', '')[:300]}")
            save_state({
                "session_id": session_id,
                "loop_until_iter": iteration,
                "loop_until_history": saved_history,
            })
            sys.exit(1)

        session_id = res["session_id"]
        output = res["output"]
        print(f"   完成: {res['num_turns']} turns, ${res['total_cost_usd']:.4f}")

        # 检查停止条件
        print(f"\n🔍 检查停止条件...")
        check_prompt = f"""[Task Output]
{output[:3000]}

[Stop Condition]
{stop_condition}

Has the stop condition been met? Output ONLY: MET or NOT_MET, followed by a brief reason."""
        check_res = run_claude(check_prompt, agent="Explore", max_turns=3)
        check_output = check_res.get("output", "").strip() if not check_res.get("error") else ""
        # 去掉 markdown 格式（**MET** → MET）再检测
        check_clean = re.sub(r'[*_`#]', '', check_output).strip()

        if check_clean.upper().startswith("MET"):
            outcome = "MET"
            print(f"   ✅ 停止条件已满足: {check_output[:120]}")
            saved_history.append({"iter": iteration, "outcome": outcome, "output_preview": output[:200]})
            total_cost = sum(h.get("cost_usd", 0) for h in saved_history)
            total_turns = sum(h.get("num_turns", 0) for h in saved_history)
            print(f"\n🎉 Loop until done 完成！")
            print(f"   总轮次: {iteration} | 累计: {total_turns} 轮, ${total_cost:.4f}")
            write_progress({"mode": "loop_until", "status": "done", "max_iterations": max_iterations,
                "current_iteration": iteration, "cost_usd": total_cost,
                "tasks": [{"iter": h["iter"], "status": "done"} for h in saved_history]})
            clear_progress()
            save_state({"session_id": None, "loop_until_iter": 0, "loop_until_history": []})
            print(f"\n{'='*60}")
            print(output)
            return
        else:
            outcome = f"NOT_MET: {check_output[:100]}"
            print(f"   ⏳ 未满足: {check_output[:120]}")

        saved_history.append({
            "iter": iteration, "outcome": outcome,
            "output_preview": output[:200],
            "cost_usd": res["total_cost_usd"],
            "num_turns": res["num_turns"],
        })
        save_state({
            "session_id": session_id,
            "loop_until_iter": iteration,
            "loop_until_history": saved_history,
        })

        # 更新进度
        write_progress({"mode": "loop_until", "status": "running", "max_iterations": max_iterations,
            "current_iteration": iteration,
            "cost_usd": sum(h.get("cost_usd", 0) for h in saved_history),
            "tasks": [{"iter": h["iter"], "status": "done", "outcome": h.get("outcome", "")[:60]} for h in saved_history]})

    print(f"\n⚠️ 达到最大轮数 {max_iterations}，停止条件仍未满足")
    total_cost = sum(h.get("cost_usd", 0) for h in saved_history)
    total_turns = sum(h.get("num_turns", 0) for h in saved_history)
    print(f"   累计: {total_turns} 轮, ${total_cost:.4f}")
    print(f"\n{'='*60}")
    print(f"📋 最后一轮输出:")
    print(f"{'='*60}")
    print(output)



# ── 参数解析: classify ────────────────────────────────────────
def _parse_classify_args(args: list) -> tuple:
    classify_prompt = ""
    actions = {}
    default_action = ""
    i = 0
    current_class = None
    while i < len(args):
        if args[i] == "--classify" and i + 1 < len(args):
            classify_prompt = args[i + 1]
            i += 2
        elif args[i] == "--default" and i + 1 < len(args):
            default_action = args[i + 1]
            i += 2
        elif args[i].startswith("--class-") and i + 1 < len(args):
            key = args[i].replace("--class-", "")
            actions[key] = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and not classify_prompt:
            classify_prompt = args[i]
            i += 1
        else:
            i += 1
    if not classify_prompt:
        print("❌ classify 需要 --classify 或 positional prompt")
        sys.exit(1)
    return classify_prompt, actions, default_action


# ── 参数解析: fanout ──────────────────────────────────────────
def _parse_fanout_args(args: list) -> tuple:
    main_prompt = ""
    subtasks = []
    synthesize_prompt = ""
    agent = None
    current = None
    i = 0
    while i < len(args):
        if args[i] == "--subtask" and i + 1 < len(args):
            if current:
                subtasks.append(current)
            current = {"prompt": args[i + 1], "name": f"task-{len(subtasks)+1}"}
            i += 2
        elif args[i] == "--synthesize" and i + 1 < len(args):
            if current:
                subtasks.append(current)
                current = None
            synthesize_prompt = args[i + 1]
            i += 2
        elif args[i] == "--agent" and i + 1 < len(args):
            if current:
                current["agent"] = args[i + 1]
            else:
                agent = args[i + 1]
            i += 2
        elif args[i] == "--name" and i + 1 < len(args) and current:
            current["name"] = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and not main_prompt:
            main_prompt = args[i]
            i += 1
        else:
            i += 1
    if current:
        subtasks.append(current)
    if not main_prompt and not subtasks:
        print("❌ fanout 需要 --subtask 或 positional prompt")
        sys.exit(1)
    return main_prompt, subtasks, synthesize_prompt, agent


# ── 参数解析: verify ──────────────────────────────────────────
def _parse_verify_args(args: list) -> tuple:
    task_prompt = ""
    rubric = ""
    verifier_agent = "Explore"
    max_rounds = 2
    i = 0
    while i < len(args):
        if args[i] == "--rubric" and i + 1 < len(args):
            rubric = args[i + 1]
            i += 2
        elif args[i] == "--verifier-agent" and i + 1 < len(args):
            verifier_agent = args[i + 1]
            i += 2
        elif args[i] == "--max-rounds" and i + 1 < len(args):
            max_rounds = _safe_int(args[i + 1], "--max-rounds", 2)
            i += 2
        elif not args[i].startswith("--") and not task_prompt:
            task_prompt = args[i]
            i += 1
        else:
            i += 1
    if not task_prompt:
        print("❌ verify 需要 positional task prompt")
        sys.exit(1)
    return task_prompt, rubric, verifier_agent, max_rounds


# ── 参数解析: genfilter ───────────────────────────────────────
def _parse_genfilter_args(args: list) -> tuple:
    gen_prompt = ""
    count = 3
    rubric = ""
    filter_prompt = ""
    filter_top = 1
    agent = None
    i = 0
    while i < len(args):
        if args[i] == "--count" and i + 1 < len(args):
            count = _safe_int(args[i + 1], "--count", 3)
            i += 2
        elif args[i] == "--rubric" and i + 1 < len(args):
            rubric = args[i + 1]
            i += 2
        elif args[i] == "--filter-prompt" and i + 1 < len(args):
            filter_prompt = args[i + 1]
            i += 2
        elif args[i] == "--filter-top" and i + 1 < len(args):
            filter_top = _safe_int(args[i + 1], "--filter-top", 1)
            i += 2
        elif args[i] == "--agent" and i + 1 < len(args):
            agent = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and not gen_prompt:
            gen_prompt = args[i]
            i += 1
        else:
            i += 1
    if not gen_prompt:
        print("❌ genfilter 需要 positional generation prompt")
        sys.exit(1)
    return gen_prompt, count, rubric, filter_prompt, filter_top, agent


# ── 参数解析: tournament ──────────────────────────────────────
def _parse_tournament_args(args: list) -> tuple:
    task_prompt = ""
    contestants = 3
    judge_prompt = ""
    agent = None
    model = None
    i = 0
    while i < len(args):
        if args[i] == "--contestants" and i + 1 < len(args):
            contestants = _safe_int(args[i + 1], "--contestants", 3)
            i += 2
        elif args[i] == "--judge" and i + 1 < len(args):
            judge_prompt = args[i + 1]
            i += 2
        elif args[i] == "--agent" and i + 1 < len(args):
            agent = args[i + 1]
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and not task_prompt:
            task_prompt = args[i]
            i += 1
        else:
            i += 1
    if not task_prompt:
        print("❌ tournament 需要 positional task prompt")
        sys.exit(1)
    return task_prompt, contestants, judge_prompt, agent, model


# ── 参数解析: loop_until ──────────────────────────────────────
def _parse_loop_until_args(args: list) -> tuple:
    task_prompt = ""
    stop_condition = ""
    max_iterations = 10
    agent = None
    i = 0
    while i < len(args):
        if args[i] == "--stop-condition" and i + 1 < len(args):
            stop_condition = args[i + 1]
            i += 2
        elif args[i] == "--max-iterations" and i + 1 < len(args):
            max_iterations = _safe_int(args[i + 1], "--max-iterations", 10)
            i += 2
        elif args[i] == "--agent" and i + 1 < len(args):
            agent = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and not task_prompt:
            task_prompt = args[i]
            i += 1
        else:
            i += 1
    if not task_prompt:
        print("❌ loop_until 需要 positional task prompt")
        sys.exit(1)
    if not stop_condition:
        print("❌ loop_until 需要 --stop-condition")
        sys.exit(1)
    return task_prompt, stop_condition, max_iterations, agent

if __name__ == "__main__":
    main()
