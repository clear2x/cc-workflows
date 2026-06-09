#!/usr/bin/env python3
"""
claude_orchestrator.py — 多 Agent 动态工作流调度器
基于 claude -p 实现：单 agent 执行、多 agent 流水线、条件分支、并行派发、长任务自动循环（最多 100 段）。

用法:
  python3 claude_orchestrator.py agents
  python3 claude_orchestrator.py run "任务描述" --agent general-purpose
  python3 claude_orchestrator.py pipeline --step "探索:列出所有 .py 文件" --agent Explore --step "分析:评估复杂度" --agent general-purpose
  python3 claude_orchestrator.py parallel --task "分析 a.py" --agent Explore --name a --task "分析 b.py" --agent Explore --name b
  python3 claude_orchestrator.py loop "Step 1: list files\nStep 2: report" --max-steps 100

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
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, List, Dict

# ── 基础工具函数 ──────────────────────────────────────
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
PROJECT_DIR = _detect_project_dir()
WORKTREE_BASE = Path("/tmp/orchestrator-worktrees")
CLAUDE_TIMEOUT = 300


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
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=CLAUDE_TIMEOUT,
        cwd=run_cwd,
        env=env,
    )

    if result.returncode != 0:
        return {
            "error": True,
            "stderr": result.stderr[:2000],
            "stdout": result.stdout[:500],
        }

    events = _parse_claude_output(result.stdout)
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
        "error": False,
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
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ── 模式 1: 查看可用 agent ───────────────────────────
def cmd_agents():
    """列出所有可用 agent（从 system init 事件读取，不依赖模型输出）"""
    cmd = [
        "claude", "-p", "echo ready",
        "--dangerously-skip-permissions",
        "--output-format", "json",
        "--max-turns", "1",
    ]
    env = os.environ.copy()
    env.pop("CLAUDE_CODE_AUTO_COMPACT", None)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, cwd=str(PROJECT_DIR), env=env,
    )
    events = _parse_claude_output(result.stdout)
    init = next((e for e in events if isinstance(e, dict) and e.get("type") == "system" and e.get("subtype") == "init"), None)
    if not init:
        print("❌ 无法读取系统初始化信息")
        if result.stderr:
            print(f"   stderr: {result.stderr[:300]}")
        sys.exit(1)
    agents = init.get("agents", [])
    print("可用 Agents:")
    for a in agents:
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
    state = load_state()
    session_id = state.get("session_id")

    if not session_id:
        first = steps[0]
        print(f"🚀 流水线启动: Step 1/{len(steps)}")
        res = run_claude(first["prompt"], agent=first.get("agent"))
        if res.get("error"):
            print(f"❌ Step 1 失败: {res.get('stderr', '')[:300]}")
            sys.exit(1)
        session_id = res["session_id"]
        state = {"session_id": session_id, "next_step": 2, "history": [{
            "step": 1, "agent": first.get("agent"),
            "stop_reason": res["stop_reason"], "num_turns": res["num_turns"],
            "cost_usd": res["total_cost_usd"], "output": res["output"][:500],
        }]}
        save_state(state)
        _print_step_result(1, res)
        steps = steps[1:]

    total_steps = len(steps) + (state.get("next_step", 2) - 1)
    for i, step_cfg in enumerate(steps, start=state.get("next_step", 2)):
        print(f"\n🔄 Step {i}/{total_steps}...")
        res = run_claude(step_cfg["prompt"], session_id, agent=step_cfg.get("agent"))
        if res.get("error"):
            print(f"❌ Step {i} 失败: {res.get('stderr', '')[:300]}")
            sys.exit(1)

        session_id = res["session_id"]
        state["session_id"] = session_id
        state["next_step"] = i + 1
        state["history"].append({
            "step": i, "agent": step_cfg.get("agent"),
            "stop_reason": res["stop_reason"], "num_turns": res["num_turns"],
            "cost_usd": res["total_cost_usd"], "output": res["output"][:500],
        })
        save_state(state)
        _print_step_result(i, res)

    print(f"\n🎉 流水线完成！共 {len(state['history'])} 步")
    total_cost = sum(h["cost_usd"] for h in state["history"])
    total_turns = sum(h["num_turns"] for h in state["history"])
    print(f"   累计: {total_turns} 轮, ${total_cost:.4f}")


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
    state = load_state()
    session_id = state.get("session_id")
    executed = set()

    if not session_id:
        first = steps[0]
        print(f"🚀 分支流水线启动: Step 1/{len(steps)}")
        res = run_claude(first["prompt"], agent=first.get("agent"))
        if res.get("error"):
            print(f"❌ Step 1 失败: {res.get('stderr', '')[:300]}")
            sys.exit(1)
        session_id = res["session_id"]
        context = {"last_output": res["output"], "last_turns": res["num_turns"]}
        state = {"session_id": session_id, "next_step": 1, "history": [], "context": context}
        save_state(state)
        _print_step_result(1, res)
        executed.add(0)
        step_idx = 1
    else:
        context = state.get("context", {})
        step_idx = state.get("next_step", 0)

    cond_step_idx = next((i for i, s in enumerate(steps) if "condition" in s), None)

    while step_idx < len(steps):
        step_cfg = steps[step_idx]
        current_step_num = step_idx + 1

        print(f"\n🔄 Step {current_step_num}/{len(steps)}...")
        res = run_claude(step_cfg["prompt"], session_id, agent=step_cfg.get("agent"))
        if res.get("error"):
            print(f"❌ Step {current_step_num} 失败")
            sys.exit(1)

        session_id = res["session_id"]
        context["last_output"] = res["output"]
        context["last_turns"] = res["num_turns"]
        executed.add(step_idx)

        state["session_id"] = session_id
        state["context"] = context
        state["history"].append({
            "step": current_step_num, "agent": step_cfg.get("agent"),
            "stop_reason": res["stop_reason"], "num_turns": res["num_turns"],
            "cost_usd": res["total_cost_usd"],
        })
        save_state(state)
        _print_step_result(current_step_num, res)

        if step_idx == cond_step_idx:
            cond_result = evaluate_condition(condition, context)
            print(f"\n🔀 条件评估: '{condition}' → {'TRUE' if cond_result else 'FALSE'}")
            next_idx = then_step_idx if cond_result else else_step_idx
            if next_idx in executed:
                print(f"⚠️ Step {next_idx + 1} 已执行过，跳到下一步")
                next_idx += 1
            step_idx = next_idx
        else:
            step_idx += 1

    print(f"\n🎉 分支流水线完成！")


# ── 模式 5: 并行派发 ──────────────────────────────────
def _run_single_task(task_cfg: dict, worktree_base: Optional[str] = None) -> dict:
    """单个并行任务"""
    name = task_cfg.get("name", "unnamed")
    prompt = task_cfg["prompt"]
    agent = task_cfg.get("agent")
    model = task_cfg.get("model")
    use_worktree = task_cfg.get("worktree", True)

    worktree_path = None
    try:
        if use_worktree and worktree_base:
            worktree_path = Path(worktree_base) / f"orchestrator-{name}"
            branch_name = f"orchestrator-{name}"

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
            "session_id": res["session_id"],
            "output": res["output"][:1000],
            "num_turns": res["num_turns"],
            "cost_usd": res["total_cost_usd"],
            "worktree": str(worktree_path) if worktree_path else None,
        }
    finally:
        keep = task_cfg.get("keep_worktree", False)
        merged = False

        if worktree_path and worktree_path.exists() and not keep:
            branch_name = f"orchestrator-{name}"
            merge_result = subprocess.run(
                ["git", "merge", "--no-edit", branch_name],
                capture_output=True, text=True, timeout=30, cwd=str(PROJECT_DIR),
            )
            if merge_result.returncode == 0:
                print(f"  🔗 [{name}] 已合并到当前分支")
                merged = True
            else:
                print(f"  ⚠️ [{name}] 合并冲突，worktree 保留: {worktree_path}")
                print(f"     解决冲突后手动合并: cd {PROJECT_DIR} && git merge --no-edit {branch_name}")
                keep = True
                merged = True

        if worktree_path and worktree_path.exists() and not keep and not merged:
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path)],
                capture_output=True, text=True, timeout=15, cwd=str(PROJECT_DIR),
            )
            print(f"  🧹 [{name}] worktree 已清理")
        elif worktree_path and worktree_path.exists() and keep and not merged:
            print(f"  📦 [{name}] worktree 已保留: {worktree_path}")


def cmd_parallel(tasks: list):
    """并行执行多个任务"""
    print(f"🔄 并行执行 {len(tasks)} 个任务...")

    results = []
    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as executor:
        futures = {executor.submit(_run_single_task, t, str(WORKTREE_BASE)): t for t in tasks}
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

        remaining_after = remaining[i + 1:]
        if not remaining_after:
            total_cost = sum(h["cost_usd"] for h in history)
            total_turns = sum(h["num_turns"] for h in history)
            print(f"\n🎉 全部 {len(all_steps)} 步完成！累计 {total_turns} 轮, ${total_cost:.4f}")
            save_state({"session_id": None, "remaining_steps": [], "history": [], "next_step": 1})
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
        print(f"   再次运行即可继续: python3 claude_orchestrator.py loop \"<原prompt>\" --max-steps {max_steps}")


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

    sessions = json.loads(result.stdout)
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


# ── 入口 ──────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 claude_orchestrator.py agents                          # 查看 agent")
        print("  python3 claude_orchestrator.py run \"任务\" [--agent X] [--model Y]")
        print("  python3 claude_orchestrator.py sessions                        # 查看会话")
        print()
        print("  流水线 (pipeline):")
        print('  python3 claude_orchestrator.py pipeline \\')
        print('    --step "探索:列出 .py 文件" --agent Explore \\')
        print('    --step "分析:评估复杂度" --agent general-purpose \\')
        print('    --step "规划:给出方案" --agent Plan')
        print()
        print("  条件分支 (branch):")
        print('  python3 claude_orchestrator.py branch \\')
        print('    --step "扫描:统计高危问题数" --agent Explore \\')
        print('    --step "报告" --agent general-purpose \\')
        print('    --step "修复" --agent general-purpose \\')
        print('    --step "跳过" --agent general-purpose \\')
        print('    --if "bugs_found > 0" --then-step 3 --else-step 4')
        print()
        print("  并行 (parallel):")
        print('  python3 claude_orchestrator.py parallel \\')
        print('    --task "分析 a.py" --agent Explore --name a \\')
        print('    --task "分析 b.py" --agent Explore --name b')
        print()
        print("  长任务 (loop):")
        print('  python3 claude_orchestrator.py loop "重构代码库" --max-steps 100')
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
    else:
        print(f"❌ 未知命令: {action}")
        print("支持: agents, run, pipeline, branch, parallel, loop, sessions")
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
            current_step["then"] = int(args[i + 1])
            i += 2
        elif args[i] == "--else-step" and i + 1 < len(args):
            current_step["else"] = int(args[i + 1])
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
            max_steps = int(args[i + 1])
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


if __name__ == "__main__":
    main()
