<div align="center">

[English](#english) | [中文](./README.zh.md)

</div>

---

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Claude Code](https://img.shields.io/badge/Claude_Code-v2.1.168%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)

</div>

<div align="center">

**A professional multi-agent workflow orchestrator for Claude Code.**

</div>

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [6 Execution Modes](#6-execution-modes)
  - [Mode 1 — `agents`](#mode-1--agents)
  - [Mode 2 — `run`](#mode-2--run)
  - [Mode 3 — `pipeline`](#mode-3--pipeline)
  - [Mode 4 — `branch`](#mode-4--branch)
  - [Mode 5 — `parallel`](#mode-5--parallel)
  - [Mode 6 — `loop`](#mode-6--loop)
  - [`sessions`](#sessions)
- [CLI Reference](#cli-reference)
- [Advanced Features](#advanced-features)
- [Superpowers Integration](#superpowers-integration)
- [Output Parsing](#output-parsing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

<a name="english"></a>
## Overview

Claude Orchestrator is a **production-grade** Python wrapper around `claude -p` (Claude Code's non-interactive headless mode). It turns one-off prompts into **repeatable, resumable, observable** workflows — without leaving your terminal.

### Execution Modes

| Mode | Description |
|------|-------------|
| `run` | Single-agent execution with auto-resume |
| `pipeline` | Sequential multi-agent pipeline |
| `branch` | Conditional branching pipeline |
| `parallel` | Parallel fan-out with git worktree isolation |
| `loop` | Long-horizon segmented loop with breakpoint-resume |
| `sessions` | Inspect active Claude sessions |

### Quick Start

```bash
# 1. Install (one-line)
npx skills add https://github.com/clear2x/claude-orchestrator

# 2. Verify agents available
python3 ~/.hermes/skills/claude-orchestrator/claude_orchestrator.py agents

# 3. Run a single task
python3 ~/.hermes/skills/claude-orchestrator/claude_orchestrator.py run \
  "Refactor auth.py, add type hints" \
  --agent general-purpose

# 4. Long multi-step task (auto-resumes on re-run)
python3 ~/.hermes/skills/claude-orchestrator/claude_orchestrator.py loop \
  "Step 1: list Python files
Step 2: read calculator.py and summarize
Step 3: read logger.py and summarize
Step 4: write a refactor plan" \
  --max-steps 100
```

## Installation

### Option A: `npx skills add` (recommended)

```bash
npx skills add https://github.com/clear2x/claude-orchestrator
```

This copies the `skills/claude-orchestrator/` folder into your local skills directory automatically.

Install a single skill by install name:

```bash
npx skills add https://github.com/clear2x/claude-orchestrator --skill "claude-orchestrator"
```

### Option B: `install.py`

```bash
git clone https://github.com/clear2x/claude-orchestrator.git
cd claude-orchestrator
python3 install.py
```

Copies the script to:
- `~/.hermes/skills/claude-orchestrator/claude_orchestrator.py` — Hermes Agent
- `~/.claude/skills/claude-orchestrator/claude_orchestrator.py` + `SKILL.md` — Claude Code

### Option C: Manual copy

```bash
# Claude Code project-level
mkdir -p .claude/skills/claude-orchestrator
cp skills/claude-orchestrator/claude_orchestrator.py .claude/skills/claude-orchestrator/
cp skills/claude-orchestrator/SKILL.md .claude/skills/claude-orchestrator/
```

```bash
# Hermes Agent global
mkdir -p ~/.hermes/skills/claude-orchestrator
cp skills/claude-orchestrator/claude_orchestrator.py ~/.hermes/skills/claude-orchestrator/
```

## 6 Execution Modes

### Mode 1 — `agents`

List all available Claude Code agents without invoking a model.

```bash
python3 claude_orchestrator.py agents
```

```
可用 Agents:
  • Explore
  • Plan
  • general-purpose
  • claude
  ...
```

### Mode 2 — `run`

Execute a single prompt with an optional agent, auto-resuming from the last session on re-run.

```bash
python3 claude_orchestrator.py run "任务描述" --agent Explore
python3 claude_orchestrator.py run "任务描述" --agent Plan --model step-3.7-flash
```

Output includes per-run metadata:

```
✅ Step 1 | end_turn | 3 turns | $0.0123
🤖 Model: step-3.7-flash
<output>
```

### Mode 3 — `pipeline`

Run multiple steps **sequentially**, each step can use a different agent. Session is carried forward automatically.

```bash
python3 claude_orchestrator.py pipeline \
  --step "Explore: list all .py files under src/" --agent Explore \
  --step "Analyze: estimate cyclomatic complexity of each file" --agent general-purpose \
  --step "Plan: produce a refactor plan" --agent Plan
```

### Mode 4 — `branch`

Sequential pipeline with **conditional branching**. After a designated evaluation step, the orchestrator jumps to either the `--then-step` or the `--else-step`.

```bash
python3 claude_orchestrator.py branch \
  --step "Scan: count HIGH severity bugs. Output: bugs_found = <number>" --agent Explore \
  --step "Report: summarize findings" --agent general-purpose \
  --step "Fix: produce a fix plan (executed when bugs found)" --agent general-purpose \
  --step "Skip: record 'no issues' (executed when no bugs)" --agent general-purpose \
  --if "bugs_found > 0" --then-step 3 --else-step 4
```

Supported condition syntax:

| Syntax | Example |
|--------|---------|
| Numeric comparison | `bugs_found > 0`, `count >= 5`, `severity == 3` |
| String contains | `output contains 'PASS'`, `result contains 'error'` |

### Mode 5 — `parallel`

Run multiple tasks **concurrently** (up to 8 workers). Each task gets its own session and an isolated **git worktree** under `/tmp/orchestrator-worktrees/orchestrator-<name>`. By default the script **auto-merges** each branch back and cleans the worktree when the task finishes.

```bash
python3 claude_orchestrator.py parallel \
  --task "Analyze src/auth.py and list security issues" --agent Explore --name auth \
  --task "Analyze src/api.py and list security issues" --agent Explore --name api \
  --task "Analyze src/db.py and list security issues" --agent Explore --name db
```

Output:

```
🔄 并行执行 3 个任务...
  🌳 [auth] worktree: /tmp/orchestrator-worktrees/orchestrator-auth
  🌳 [api] worktree: /tmp/orchestrator-worktrees/orchestrator-api
  🌳 [db] worktree: /tmp/orchestrator-worktrees/orchestrator-db
  🚀 [auth] 启动...
  🚀 [api] 启动...
  🚀 [db] 启动...
  ✅ [auth] end_turn, 4 turns, $0.0234
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

### Mode 6 — `loop`

Split a multi-line prompt into independent steps. Execute them one by one, saving state after each step so you can **interrupt and resume**.

```bash
python3 claude_orchestrator.py loop \
  "Step 1: list all Python files under src/
Step 2: read auth.py and summarize its structure
Step 3: read api.py and summarize its structure
Step 4: write a refactor plan covering both files" \
  --max-steps 100 \
  --agent Explore
```

Breakpoint-resume behaviour:

```bash
# First run: only 2 steps allowed
python3 claude_orchestrator.py loop "..." --max-steps 2
# → ⏸️ 本次执行 2 段完成，还剩 2 步未执行

# Second run: same command, resumes from Step 3
python3 claude_orchestrator.py loop "..." --max-steps 2
# → 🔄 从上次中断处继续，还剩 2 步... Step 3 → Step 4
```

State is stored at `/tmp/claude_orchestrator_state.json` and survives process restarts.

### `sessions`

Inspect active background Claude sessions and the orchestrator's own tracked state.

```bash
python3 claude_orchestrator.py sessions
```

## CLI Reference

```
python3 claude_orchestrator.py <command> [options]

commands:
  agents                              List available agents
  run <prompt> [--agent X] [--model Y]   Single-agent execution
  pipeline --step "X" --agent Y [...]   Sequential multi-agent pipeline
  branch  --step "X" --agent Y [...]    Conditional branching pipeline
  parallel --task "X" --agent Y --name Z [...]   Parallel fan-out
  loop <prompt> [--max-steps N] [--agent X] [--interactive]   Segmented loop
  sessions                             Inspect sessions

global:
  --dangerously-skip-permissions       Auto-injected (no approval prompts)
  --allowedTools Read,Write,Edit,Bash,Grep,Glob,TodoWrite
  --max-turns 12                       Per-step turn limit
  --output-format json                 Structured event stream
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

Pass `--interactive` to trigger a **Superpowers brainstorming-style** pre-flight before any steps run:

1. Generates 2–3 short clarifying questions via `claude -p`
2. Prompts for answers (or `skip`)
3. Produces a refined, actionable prompt
4. Enters the normal segmented loop with the refined prompt

```
🔍 Superpowers brainstorming: 需求澄清
========================================

  Q1: What does "done" look like for this refactor?
  Q2: Which files/components are in scope?
  Q3: Any specific constraints (TDD, code review)?

  A1: All tests must pass
  A2: src/auth.py and src/api.py only
  A3: Follow TDD, require code review

📝 Refined prompt:
   Refactor src/auth.py and src/api.py using TDD: ...
```

> **Note:** `--interactive` requires a real TTY. It will fail with `EOFError` inside non-interactive subprocesses (Claude Code sub-agents, CI pipes).

## Superpowers Integration

[Superpowers](https://github.com/obra/superpowers) (by obra) is a set of coding-agent best-practice skills: TDD, subagent-driven-development, writing-plans, requesting-code-review, systematic-debugging, and brainstorming.

Claude Orchestrator integrates with Superpowers in two ways:

1. **Auto-injection** — the `loop` mode detects workflow keywords and prepends the matching constraint text before each step.
2. **Manual combination** — combine `run`/`loop` with Superpowers keywords in your prompts:

```bash
# TDD enforced via auto-injection
python3 claude_orchestrator.py loop \
  "Implement user registration using TDD" \
  --max-steps 50

# Subagent-driven development via auto-injection
python3 claude_orchestrator.py loop \
  "Refactor auth module using subagent-driven-development" \
  --max-steps 80
```

Install Superpowers as a Claude Code plugin:

```bash
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

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
| `claude: command not found` | Set the full path to the `claude` binary in `claude_orchestrator.py` (`cmd[0]`). Common path: `/Users/<user>/.local/bin/claude` |
| `EOFError` in `--interactive` | `--interactive` requires a TTY. Remove it; do clarification in the Claude Code conversation first |
| `result.result` is empty | Normal — the parser falls back to `assistant` event text blocks |
| Worktree merge conflict | The worktree is preserved at `/tmp/orchestrator-worktrees/orchestrator-<name>`. Resolve manually, then run `git merge --no-edit orchestrator-<name>` from your project root |
| State file grows large | Run `python3 claude_orchestrator.py loop "dummy" --max-steps 0` to reset (completes any pending loop and clears state) |

## License

[MIT](LICENSE) — feel free to use, modify, and distribute.
