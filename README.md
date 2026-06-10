# CC Workflows

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Claude Code](https://img.shields.io/badge/Claude_Code-v2.1.168%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)

**A collection of multi-agent workflow primitives and patterns for Claude Code.**

</div>

[English](#english) | [中文](./README.zh.md)

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Best Practices: Using in Claude Code](#best-practices-using-in-claude-code)
  - [Talk Naturally](#talk-naturally)
  - [Slash Commands](#slash-commands)
  - [Mode Selection Guide](#mode-selection-guide)
- [Installation](#installation)
- [12 Execution Modes](#12-execution-modes)
  - [`agents`](#agents)
  - [`run`](#run)
  - [`pipeline`](#pipeline)
  - [`branch`](#branch)
  - [`parallel`](#parallel)
  - [`loop`](#loop)
  - [`sessions`](#sessions)
  - [`classify`](#classify)
  - [`fanout`](#fanout)
  - [`verify`](#verify)
  - [`genfilter`](#genfilter)
  - [`tournament`](#tournament)
  - [`loop_until`](#loop_until)
- [CLI Reference](#cli-reference)
- [Advanced Features](#advanced-features)
- [Superpowers Integration](#superpowers-integration)
- [Best Practices: cc-workflows × Superpowers](#best-practices-cc-workflows--superpowers)
- [Output Parsing](#output-parsing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

<a name="english"></a>
## Overview

CC Workflows is a **production-grade** Python wrapper around `claude -p` (Claude Code's non-interactive headless mode). It turns one-off prompts into **repeatable, resumable, observable** workflows — all from within your Claude Code conversation.

### 12 Execution Modes

| Mode | Description |
|------|-------------|
| `run` | Single-agent execution with auto-resume |
| `pipeline` | Sequential multi-agent pipeline |
| `branch` | Conditional branching pipeline |
| `parallel` | Parallel fan-out with git worktree isolation |
| `loop` | Long-horizon segmented loop with breakpoint-resume |
| `sessions` | Inspect active Claude sessions |
| `classify` | Classify task → route to specialized agent (Classify-and-act) |
| `fanout` | Spawn subtasks concurrently, then synthesize results (Fan-out-and-synthesize) |
| `verify` | Run task, then adversarially verify & fix in loop (Adversarial verification) |
| `genfilter` | Generate N solutions, filter with rubric, return top K (Generate-and-filter) |
| `tournament` | N contestants compete, judge picks winner (Tournament) |
| `loop_until` | Repeat until stop condition is MET (Loop until done) |

### Quick Start

```bash
# 1. Install (one-line)
npx skills add https://github.com/clear2x/cc-workflows

# Or install a single mode:
# npx skills add https://github.com/clear2x/cc-workflows --skill cc-run
```

Then open Claude Code and just talk:

```
💬 > 用 cc-workflows 帮我看看有哪些可用的 agent
💬 > 用 cc-workflows 重构 auth.py，添加类型提示
💬 > 用 cc-workflows loop 重构 src/，最多 50 步
💬 > 并行分析这三个文件：a.py, b.py, c.py
```

Claude will automatically pick the right mode and execute it.

## Best Practices: Using in Claude Code

### Talk Naturally

You do not need to memorize mode names or command syntax. Just describe what you want in plain language inside Claude Code, and Claude will automatically pick the right mode for you. Here are some examples:

| What you say | Mode Claude picks |
|---|---|
| "帮我并行分析这3个文件" (Analyze these 3 files in parallel) | `parallel` |
| "先扫描有没有问题，有的话修复" (Scan for issues first, fix if found) | `branch` |
| "让3个方案竞争选出最好的" (Let 3 approaches compete, pick the best) | `tournament` |
| "循环执行直到测试通过" (Keep looping until tests pass) | `loop_until` |
| "生成几个方案然后筛选最好的" (Generate several options then filter for the best) | `genfilter` |
| "先分类这个任务，再交给对应的 agent" (Classify this task, then route to the right agent) | `classify` |

### Slash Commands

CC Workflows registers 13 slash commands you can invoke directly in Claude Code:

| Command | Description |
|---------|-------------|
| `/cc-workflows` | **Overview of all modes — auto-selects the best mode for your task** |
| `/cc-agents` | List available agents |
| `/cc-run` | Single task execution |
| `/cc-pipeline` | Sequential pipeline |
| `/cc-branch` | Conditional branch |
| `/cc-parallel` | Parallel execution |
| `/cc-loop` | Long task loop |
| `/cc-classify` | Classify and route |
| `/cc-fanout` | Fan-out and synthesize |
| `/cc-verify` | Adversarial verification |
| `/cc-genfilter` | Generate and filter |
| `/cc-tournament` | Tournament |
| `/cc-loop-until` | Loop until condition met |

### Mode Selection Guide

Not sure which mode to use? Pick based on your task:

| Task | Recommended Mode |
|------|-----------------|
| Single task | `run` |
| Multi-step sequential | `pipeline` |
| Conditional execution | `branch` |
| Multiple tasks at once | `parallel` |
| Long task, many steps | `loop` |
| Route by task type | `classify` |
| Parallel + synthesize | `fanout` |
| Generate + quality check | `verify` |
| Generate many, pick best | `genfilter` |
| Competitive approaches | `tournament` |
| Repeat until goal met | `loop_until` |

## Installation

### Option A: `npx skills add` (recommended)

```bash
npx skills add https://github.com/clear2x/cc-workflows

# Or install a single mode skill:
# npx skills add https://github.com/clear2x/cc-workflows --skill cc-run
```

This copies all mode skills (`cc-run`, `cc-pipeline`, `cc-loop`, etc.) into your local skills directory.

### Option B: `install.py`

```bash
git clone https://github.com/clear2x/cc-workflows.git
cd cc-workflows
python3 install.py
```

Copies the script to:
- `~/.hermes/skills/cc-workflows/cc_workflows.py` — core script (Hermes Agent)
- `~/.claude/skills/cc-workflows/cc_workflows.py` + `SKILL.md` — core script (Claude Code)

### Option C: Manual copy

```bash
# Claude Code project-level
mkdir -p .claude/skills/cc-workflows
cp skills/cc-workflows/cc_workflows.py .claude/skills/cc-workflows/
cp skills/cc-workflows/SKILL.md .claude/skills/cc-workflows/
```

```bash
# Hermes Agent global
mkdir -p ~/.hermes/skills/cc-workflows
cp skills/cc-workflows/cc_workflows.py ~/.hermes/skills/cc-workflows/
```

## 12 Execution Modes

### `agents`

List all available Claude Code agents without invoking a model.

```
💬 在 Claude Code 中：
> 用 cc-workflows 帮我看看有哪些可用的 agent
```

Output:

```
可用 Agents:
  • Explore
  • Plan
  • general-purpose
  • claude
...
```

### `run`

Execute a single prompt with an optional agent, auto-resuming from the last session on re-run.

```
💬 在 Claude Code 中：
> 用 cc-workflows 的 run 模式，让 Explore agent 列出当前目录的 .py 文件

（续接上次会话）
> 再让它在上面结果基础上统计代码总行数
```

Output includes per-run metadata:

```
✅ Step 1 | end_turn | 3 turns | $0.0123
🤖 Model: step-3.7-flash
<output>
```

### `pipeline`

Run multiple steps **sequentially**, each step can use a different agent. Session is carried forward automatically.

```
💬 在 Claude Code 中：
> 用 cc-workflows pipeline 跑 3 步：先找出最大的 .py 文件，再总结它的功能，最后给 3 条优化建议
```

### `branch`

Sequential pipeline with **conditional branching**. After a designated evaluation step, the orchestrator jumps to either the `--then-step` or the `--else-step`.

```
💬 在 Claude Code 中：
> 用 cc-workflows 的 branch 模式：扫描有没有安全漏洞，有的话生成修复方案，没有的话记录无问题
```

Supported condition syntax:

| Syntax | Example |
|--------|---------|
| Numeric comparison | `bugs_found > 0`, `count >= 5`, `severity == 3` |
| String contains | `output contains 'PASS'`, `result contains 'error'` |

### `parallel`

Run multiple tasks **concurrently** (up to 8 workers). Each task gets its own session and an isolated **git worktree**. By default the script **auto-merges** each branch back and cleans the worktree when the task finishes.

```
💬 在 Claude Code 中：
> 用 cc-workflows 并行分析 3 个文件：auth.py 的安全性、api.py 的性能、db.py 的结构
```

Output:

```
🔄 并行执行 3 个任务...
  🌳 [auth] worktree: /tmp/orchestrator-worktrees/orchestrator-auth
  🚀 [auth] 启动...
  🔗 [auth] 已合并到当前分支
  🧹 [auth] worktree 已清理

📊 并行结果:
  ✅ [auth] 4 turns, $0.0234
  ✅ [api] 3 turns, $0.0189
  ✅ [db] 5 turns, $0.0312
```

Worktree flags:

| Flag | Behaviour |
|------|-----------|
| *(default)* | Create worktree → run → `git merge --no-edit` → clean up |
| `--keep-worktree` | Skip merge & cleanup; worktree kept at `/tmp/orchestrator-worktrees/orchestrator-<name>` |
| `--no-worktree` | Disable isolation; all tasks run directly in the shared project directory |

### `loop`

Split a multi-line prompt into independent steps. Execute them one by one, saving state after each step so you can **interrupt and resume**.

```
💬 在 Claude Code 中：
> 用 cc-workflows loop 跑 4 步：列文件 → 找最大文件 → 总结功能 → 给优化建议

（断点续接）
> 用 cc-workflows loop 跑 4 步任务，先只跑 2 步，然后再续接跑完
```

Breakpoint-resume behaviour:

- First run: 2 steps → ⏸️ 本次执行 2 段完成，还剩 2 步未执行
- Second run: same prompt → 🔄 从上次中断处继续，还剩 2 步... Step 3 → Step 4

State is stored at `/tmp/claude_orchestrator_state.json` and survives process restarts.

### `sessions`

Inspect active background Claude sessions and the orchestrator's own tracked state.

```
💬 在 Claude Code 中：
> 用 cc-workflows 查看当前活跃的会话
```

## Workflow Patterns

### `classify`

**Classify-and-act**: Use a classifier agent to decide the task type, then route to different agents/behaviors.

```
💬 在 Claude Code 中：
> 用 cc-workflows classify 分析这段代码的风险：SELECT * FROM users WHERE id = user_input，按 security 和 performance 分类处理
```

How it works:
1. Runs a classifier agent (`Explore` by default) on your classify prompt
2. Matches the output against your `--class-<key>` action prompts
3. Executes the matching action prompt with `general-purpose`
4. If no match, falls back to `--default`

### `fanout`

**Fan-out-and-synthesize**: Split a task into many smaller steps, run an agent on each, then synthesize results.

```
💬 在 Claude Code 中：
> 用 cc-workflows fanout 并行做 3 件事：审查 auth.py 的安全性、审查 api.py 的可扩展性、检查 README 是否完整，然后汇总成一份综合报告
```

How it works:
1. Each `--subtask` runs concurrently in its own git worktree (isolation)
2. All subtask outputs are collected
3. If `--synthesize` is provided, a final agent merges all results into one report
4. Worktrees are auto-merged and cleaned up by default (`--keep-worktree` to preserve)

### `verify`

**Adversarial verification**: Run a task, then spawn a separate verifier agent to adversarially check the output against a rubric. Repeat until PASS or max rounds reached.

```
💬 在 Claude Code 中：
> 用 cc-workflows verify 让它写一个斐波那契函数，然后验证是否包含函数定义、边界处理、复杂度说明，最多验证 2 轮
```

How it works:
1. Main agent executes the task
2. Verifier agent (`Explore` by default) scores the output against the rubric
3. If FAIL, the main agent gets the issues and produces a corrected version
4. Repeats up to `--max-rounds` times
5. Outputs the final (hopefully verified) result

### `genfilter`

**Generate-and-filter**: Generate N ideas/solutions, then filter them by a rubric, returning only the highest quality candidates.

```
💬 在 Claude Code 中：
> 用 cc-workflows genfilter 为这个项目起 3 个名字，标准是简短好记有科技感，筛出最好的 1 个
```

How it works:
1. Spawns `--count` parallel agents, each generating an independent solution
2. All results are fed to a judge agent with the rubric
3. Judge scores and ranks each solution
4. Top `--filter-top` results are returned with full details

### `tournament`

**Tournament**: Have N agents compete on the same task using different approaches, then a judge agent picks the winner.

```
💬 在 Claude Code 中：
> 用 cc-workflows tournament 让 3 个选手竞争"用一句话向程序员解释递归"，judge 按"准确、有类比、一句话说清"评分
```

How it works:
1. Spawns `--contestants` agents, each given a different "approach" framing (direct/robust/optimized/creative/standard)
2. All contestants run concurrently in isolated worktrees
3. A judge agent (`Explore`) evaluates all submissions pairwise against the task + judge prompt
4. Winner is announced with scoring breakdown

### `loop_until`

**Loop until done**: For tasks with an unknown amount of work, loop spawning agents until a stop condition is met (instead of a fixed number of passes).

```
💬 在 Claude Code 中：
> 用 cc-workflows loop_until 让它给 calculator.py 添加功能，直到包含了 sqrt、abs、round 三个函数为止，最多试 5 轮
```

How it works:
1. Executes the task prompt in a loop (with session resume between iterations)
2. After each iteration, a lightweight checker agent evaluates whether the stop condition is MET
3. If MET → exit and show final output
4. If NOT_MET → continue to next iteration (up to `--max-iterations`)
5. State is persisted to `/tmp/claude_orchestrator_state.json`, survives restarts

## CLI Reference

> **Note:** These are internal commands used by Claude Code. You should interact with cc-workflows through **natural language** or **slash commands** in your Claude Code conversation — not by running these commands directly.

```
cc_workflows.py <command> [options]

commands:
  agents                              List available agents
  run <prompt> [--agent X] [--model Y]   Single-agent execution
  pipeline --step "X" --agent Y [...]   Sequential multi-agent pipeline
  branch  --step "X" --agent Y [...]    Conditional branching pipeline
  parallel --task "X" --agent Y --name Z [...]   Parallel fan-out
  loop <prompt> [--max-steps N] [--agent X] [--interactive]   Segmented loop
  sessions                             Inspect sessions

  classify <prompt> [--class-KEY "action"] [--default "action"]   Classify-and-act
  fanout <prompt> [--subtask "X"] [--synthesize "Y"] [--agent Z]   Fan-out-and-synthesize
  verify <prompt> [--rubric "X"] [--verifier-agent Y] [--max-rounds N]   Adversarial verification
  genfilter <prompt> [--count N] [--rubric "X"] [--filter-top K]   Generate-and-filter
  tournament <prompt> [--contestants N] [--judge "X"]   Tournament
  loop_until <prompt> --stop-condition "X" [--max-iterations N]   Loop until done

global (auto-injected):
  --dangerously-skip-permissions
  --allowedTools Read,Write,Edit,Bash,Grep,Glob,TodoWrite
  --max-turns 12
  --output-format json
```


## Advanced Features

### Automatic Project Root Detection

The script runs `git rev-parse --show-toplevel` at startup. If the cwd is inside a git repo it uses that root; otherwise it falls back to `Path.cwd()`. No hardcoded paths.

### State Persistence

All multi-step modes write to `/tmp/claude_orchestrator_state.json` after every step. If a run is killed (Ctrl-C, timeout, crash), re-running the same command resumes from the last completed step — zero data loss.

### Superpowers Workflow Auto-Injection

The `loop` mode inspects each step's prompt for keywords and automatically injects the matching [Superpowers](https://github.com/obra/superpowers) constraint before the actual task text.

| Keyword pattern | Injected skill |
|-----------------|----------------|
| `tdd`, `test-driven`, `测试驱动` | test-driven-development |
| `plan`, `规划`, `拆解` | writing-plans |
| `subagent`, `并行`, `多 agent` | subagent-driven-development |
| `review`, `评审`, `code review` | requesting-code-review |
| `debug`, `调试`, `修复 bug` | systematic-debugging |
| anything else | generic workflow reminder |

This means a single `loop` step like:

```
Refactor auth.py using TDD: write failing tests first, then implement, then refactor
```

...will have the Red-Green-Refactor constraint injected automatically, no manual prompt engineering required.

### `--interactive` Pre-flight (Loop Only)

> **⚠️ Important:** `--interactive` requires a real TTY. It will fail with `EOFError` inside non-interactive subprocesses (Claude Code sub-agents, CI pipes). **Do requirement clarification in the Claude Code conversation first**, then execute without `--interactive`.

## Superpowers Integration

[Superpowers](https://github.com/obra/superpowers) (by obra) is a set of coding-agent best-practice skills: TDD, subagent-driven-development, writing-plans, requesting-code-review, systematic-debugging, and brainstorming.

CC Workflows integrates with Superpowers in two ways:

1. **Auto-injection** — the `loop` mode detects workflow keywords and prepends the matching constraint text before each step.
2. **Manual combination** — use Superpowers keywords in your conversation prompts:

```
💬 在 Claude Code 中：
> 用 cc-workflows loop 实现用户注册功能，使用 TDD，最多 50 步

> 用 cc-workflows loop 使用 subagent-driven-development 重构 auth 模块，最多 80 步
```

Install Superpowers as a Claude Code plugin:

```bash
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

## Best Practices: cc-workflows × Superpowers

### Practice 0: `/cc-workflows` — The Universal Entry Point (Recommended)

`/cc-workflows` is the **primary entry point** for all workflows. Type `/cc-workflows` followed by your task description, and Claude will:

1. **Load the full skill** — reads all 12 modes and their triggers
2. **Auto-select the best mode** — matches your natural language to the right pattern
3. **Combine with Superpowers** — if Superpowers is installed, Claude can trigger brainstorming for clarification, inject TDD constraints, or apply subagent-driven-development automatically

```
💬 在 Claude Code 中：
> /cc-workflows 重构 auth 模块，加上 OAuth2 支持

Claude will:
  → Auto-detect task type (implementation)
  → If Superpowers brainstorming is available, ask clarifying questions
  → Choose the right mode (run / loop / pipeline / etc.)
  → If TDD keywords are present, inject test-driven-development constraints
  → Execute and report results
```

**This is all you need to remember.** One slash command + natural language. Everything else is automatic.

### Core Insight: Complementary Roles

| Dimension | Superpowers | cc-workflows |
|-----------|-------------|-------------|
| **Role** | Methodology (what to do, how to do it right) | Execution engine (how to run, how to orchestrate) |
| **Focus** | TDD red-green cycle, review quality, plan discipline | Multi-agent parallelism, breakpoint resume, long-task orchestration |
| **Execution** | Inside Claude Code session (Agent tool / subagents) | `claude -p` subprocess (isolated session) |
| **Context** | Inherits main session, interactive Q&A | Isolated context, one-shot prompt |

**Key principle: Superpowers decides "what", cc-workflows decides "how to run it".**

### Practice 1: Conversation-First Workflow (Recommended)

Inside Claude Code, you **don't need to construct any commands manually**. Describe your intent naturally and Claude will:

1. Load relevant Superpowers skills (brainstorming → writing-plans → subagent-driven-development)
2. Choose the appropriate cc-workflows mode automatically

**Typical conversation flow:**

```
You: I want to add OAuth2 support to the auth module

Claude:
  → Auto-triggers brainstorming skill
  → Asks clarifying questions one at a time
  → Proposes 2-3 approaches with trade-offs
  → You approve → writes spec
  → Triggers writing-plans skill
  → Generates detailed step-by-step plan
  → Asks how to execute

You: Execute with subagent-driven-development

Claude:
  → Auto-triggers subagent-driven-development skill
  → Dispatches fresh subagent per task
  → Spec review → code quality review after each
  → Finishes with finishing-a-development-branch
```

**This flow runs entirely within the conversation — no manual cc-workflows commands needed.** Superpowers' built-in subagent mechanism already provides parallelism and isolation.

### Practice 2: Long Tasks → cc-workflows `loop` with Superpowers Constraints

When a task **exceeds 12 tool-call rounds** or needs **20+ steps**, the main session's context will overflow. Switch to cc-workflows `loop`:

```
💬 在 Claude Code 中：
> /cc-workflows loop 用 TDD 重构 auth.py，分 7 步：
> Step 1: 用 TDD 方式为 auth.py 写 OAuth2 的失败测试
> Step 2: 实现最小代码让测试通过
> Step 3: 重构，提取公共逻辑
> Step 4: 用 TDD 为 token 刷新写失败测试
> Step 5: 实现刷新逻辑
> Step 6: 运行全量测试确认无回归
> Step 7: 提交代码
> 最多 50 步
```

**Why this works:**
- `loop` auto-detects keywords (e.g., `TDD`, `test`) and injects Superpowers constraints
- Each segment clears context via `--resume`, preventing overflow
- Supports breakpoint resume — just say "继续" to pick up where it left off

### Practice 3: Parallel Exploration → cc-workflows `parallel` + Explore Agent

When you need to **analyze multiple independent subsystems simultaneously**:

```
💬 在 Claude Code 中：
> /cc-workflows parallel 并行分析 3 个维度：
> 维度 1：审查 auth.py 的安全性（SQL 注入、XSS、权限绕过）
> 维度 2：分析 api.py 的性能瓶颈（N+1 查询、缺少缓存、慢查询）
> 维度 3：检查 db.py 的数据完整性（约束缺失、竞态条件、迁移问题）
```

**When to use:**
- Code review (security / performance / maintainability in parallel)
- Independent multi-file refactoring
- Simultaneous debugging of unrelated issues

**When NOT to use:**
- Tasks have dependencies (changing A affects B)
- Global understanding is needed (one agent can't see the full picture)

### Practice 4: Verification Loop → cc-workflows `verify`

**Implement, then adversarially verify** — mirroring Superpowers' `verification-before-completion` principle:

```
💬 在 Claude Code 中：
> /cc-workflows verify 实现一个 JWT 中间件，支持 token 验证、刷新、黑名单。
> 验证标准：1. 必须有单元测试覆盖正常和异常路径 2. 必须验证 token 过期 3. 必须处理畸形 token 4. 必须遵循项目风格
> 最多验证 3 轮
```

**This is equivalent to Superpowers' spec review + code quality review, but executed through cc-workflows' isolated subprocess.**

### Practice 5: Solution Selection → `tournament` / `genfilter`

**Competing approaches** (mirrors Superpowers brainstorming's "propose 2-3 approaches"):

```
💬 在 Claude Code 中：
> /cc-workflows tournament 让 3 个选手竞争"实现一个线程安全的 LRU 缓存"，
> judge 按"线程安全正确、O(1) 读写、代码简洁、测试充分"评分

> /cc-workflows genfilter 为 REST API 设计 3 种错误处理方案，
> 标准：统一格式、包含错误码、支持国际化，筛出最好的 1 个
```

### Decision Tree: Which Tool When?

```
Have a requirement?
├─ Unclear requirements → Superpowers brainstorming (in conversation)
├─ Clear requirements, need a plan → Superpowers writing-plans (in conversation)
├─ Have a plan, need to execute
│   ├─ Task < 12 rounds → Superpowers subagent-driven-development (Agent tool)
│   ├─ Task > 12 rounds → /cc-workflows loop (run in background)
│   ├─ Multiple parallel tasks → /cc-workflows parallel or fanout
│   └─ Need verification → /cc-workflows verify
├─ Choosing best approach → /cc-workflows tournament or genfilter
├─ Loop until goal met → /cc-workflows loop_until
└─ Unsure which path → /cc-workflows (auto-select)
```

### Quick Reference: Recommended Combinations

| Scenario | Superpowers Skill | cc-workflows Mode | Trigger |
|----------|------------------|-------------------|---------|
| **Any task (universal entry)** | auto-detect | **auto-select** | `/cc-workflows <task>` |
| Explore requirements | brainstorming | — | Natural language in conversation |
| Create implementation plan | writing-plans | — | Natural language in conversation |
| Small task implementation | subagent-driven-development | — | Conversation or `/cc-run` |
| Long TDD task | test-driven-development | `loop` | `/cc-loop` + TDD keyword auto-inject |
| Multi-file parallel analysis | dispatching-parallel-agents | `parallel` | `/cc-parallel` |
| Parallel + synthesize | — | `fanout` | `/cc-fanout` |
| Post-implementation verification | verification-before-completion | `verify` | `/cc-verify` |
| Conditional execution | — | `branch` | `/cc-branch` |
| Competing approaches | brainstorming (proposal phase) | `tournament` | `/cc-tournament` |
| Loop until goal met | — | `loop_until` | `/cc-loop-until` |
| Task classification & routing | — | `classify` | `/cc-classify` |
| Code review | requesting-code-review | `pipeline` | `/cc-pipeline` |

### Common Pitfalls

| Pitfall | Correct Approach |
|---------|-----------------|
| Running `python3 cc_workflows.py` directly | ❌ Use natural language or slash commands in Claude Code conversation |
| Using `--interactive` in cc-workflows | ❌ Claude Code subprocess has no TTY → `EOFError`. Do clarification in conversation first |
| Trusting agent "success" reports | ❌ Use Superpowers verification-before-completion: run tests, read output, then conclude |
| Stuffing a huge prompt into one `loop` step | ❌ Keep each segment under 2000 chars — split into more steps instead |
| Running long tasks until context overflows | ❌ Switch to `/cc-loop` after ~20 steps; rely on resume for context management |
| Using `parallel` for dependent tasks | ❌ Only use `parallel` for independent tasks; use `pipeline` for dependencies |
| Skipping review | ❌ Superpowers requires spec review + code quality review — never skip |

## Output Parsing

Claude Code's `--output-format json` often emits the assistant's actual text in preceding `assistant` events (`message.content[].text`), not in the final `result.result` field (which is frequently `""`). The orchestrator's `_parse_claude_output` and extraction logic handles both paths:

```python
# 1. Try result.result
output = last_result.get("result") or ""

# 2. Fallback: concatenate all assistant text blocks
if not output.strip():
    text_parts = [
        block["text"]
        for e in events if e.get("type") == "assistant"
        for block in e.get("message", {}).get("content", [])
        if block.get("type") == "text"
    ]
    output = "\n".join(text_parts).strip()
```

Model name is resolved from `result.modelUsage` keys when `result.model` is `null`.

See [`references/output-parsing.md`](references/output-parsing.md) for the full event-structure reference.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `claude: command not found` | Set the full path to the `claude` binary in `cc_workflows.py` (`cmd[0]`). Common path: `/Users/<user>/.local/bin/claude` |
| `EOFError` in `--interactive` | `--interactive` requires a TTY. Remove it; do clarification in the Claude Code conversation first |
| `result.result` is empty | Normal — the parser falls back to `assistant` event text blocks |
| Worktree merge conflict | The worktree is preserved at `/tmp/orchestrator-worktrees/orchestrator-<name>`. Resolve manually, then run `git merge --no-edit orchestrator-<name>` from your project root |
| State file grows large | Run `python3 cc_workflows.py loop "dummy" --max-steps 0` to reset (completes any pending loop and clears state) |

## License

[MIT](LICENSE) — feel free to use, modify, and distribute.
