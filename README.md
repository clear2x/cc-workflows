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
- [Installation](#installation)
- [12 Execution Modes](#12-execution-modes)
  - [Primitive 1 — `agents`](#primitive-1--agents)
  - [Primitive 2 — `run`](#primitive-2--run)
  - [Primitive 3 — `pipeline`](#primitive-3--pipeline)
  - [Primitive 4 — `branch`](#primitive-4--branch)
  - [Primitive 5 — `parallel`](#primitive-5--parallel)
  - [Primitive 6 — `loop`](#primitive-6--loop)
  - [`sessions`](#sessions)
  - [Pattern 1 — `classify`](#pattern-1--classify)
  - [Pattern 2 — `fanout`](#pattern-2--fanout)
  - [Pattern 3 — `verify`](#pattern-3--verify)
  - [Pattern 4 — `genfilter`](#pattern-4--genfilter)
  - [Pattern 5 — `tournament`](#pattern-5--tournament)
  - [Pattern 6 — `loop_until`](#pattern-6--loop_until)
- [CLI Reference](#cli-reference)
- [Advanced Features](#advanced-features)
- [Superpowers Integration](#superpowers-integration)
- [Output Parsing](#output-parsing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

<a name="english"></a>
## Overview

CC Workflows is a **production-grade** Python wrapper around `claude -p` (Claude Code's non-interactive headless mode). It turns one-off prompts into **repeatable, resumable, observable** workflows — without leaving your terminal.

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

# 2. Verify agents available
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py agents

# 3. Run a single task
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py run \
  "Refactor auth.py, add type hints" \
  --agent general-purpose

# 4. Long multi-step task (auto-resumes on re-run)
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py loop \
  "Step 1: list Python files
Step 2: read calculator.py and summarize
Step 3: read logger.py and summarize
Step 4: write a refactor plan" \
  --max-steps 100
```

### How This Compares to Official Dynamic Workflows

Claude Code's official [dynamic workflows](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) let Claude **write and orchestrate its own JavaScript harness** on the fly. That system exposes 6 workflow **design patterns** (Classify-and-act, Fan-out-and-synthesize, Adversarial verification, Generate-and-filter, Tournament, Loop until done) that Claude composes as JS code inside a workflow file.

CC Workflows takes a different approach: it provides 6 CLI **execution primitives** — fixed, opinionated command modes that wrap `claude -p` and handle orchestration concerns (worktrees, state, resume, Superpowers injection) so you don't have to write any JS.

| Official pattern | Closest Orchestrator mode | Notes |
|------------------|---------------------------|-------|
| Classify-and-act | `branch` | Route to different steps based on a condition |
| Fan-out-and-synthesize | `parallel` | Spawn concurrent agents; manual synthesis in a follow-up step |
| Adversarial verification | `pipeline` + `parallel` | Chain a verifier agent after each worker in a pipeline |
| Generate-and-filter | `pipeline` | Generate step then filter/review step |
| Tournament | `parallel` | Spawn N agents on the same task, then judge results |
| Loop until done | `loop` | Segmented loop with stop condition (max-steps acts as budget) |

In short: official dynamic workflows are **Claude-authored, JS-based, and flexible**; CC Workflows is **user-invoked, CLI-driven, and convention-based**. Use CC Workflows when you want predictable, reusable, shareable commands without writing workflow JS.

## Installation

### Option A: `npx skills add` (recommended)

```bash
npx skills add https://github.com/clear2x/cc-workflows
```

This copies the `skills/cc-workflows/` folder into your local skills directory automatically.

Install a single skill by install name:

```bash
npx skills add https://github.com/clear2x/cc-workflows --skill "cc-workflows"
```

### Option B: `install.py`

```bash
git clone https://github.com/clear2x/cc-workflows.git
cd cc-workflows
python3 install.py
```

Copies the script to:
- `~/.hermes/skills/cc-workflows/claude_orchestrator.py` — Hermes Agent
- `~/.claude/skills/cc-workflows/claude_orchestrator.py` + `SKILL.md` — Claude Code

### Option C: Manual copy

```bash
# Claude Code project-level
mkdir -p .claude/skills/cc-workflows
cp skills/cc-workflows/claude_orchestrator.py .claude/skills/cc-workflows/
cp skills/cc-workflows/SKILL.md .claude/skills/cc-workflows/
```

```bash
# Hermes Agent global
mkdir -p ~/.hermes/skills/cc-workflows
cp skills/cc-workflows/claude_orchestrator.py ~/.hermes/skills/cc-workflows/
```

## 12 Execution Modes

### Primitive 1 — `agents`

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

### Primitive 2 — `run`

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

### Primitive 3 — `pipeline`

Run multiple steps **sequentially**, each step can use a different agent. Session is carried forward automatically.

```bash
python3 claude_orchestrator.py pipeline \
  --step "Explore: list all .py files under src/" --agent Explore \
  --step "Analyze: estimate cyclomatic complexity of each file" --agent general-purpose \
  --step "Plan: produce a refactor plan" --agent Plan
```

### Primitive 4 — `branch`

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

### Primitive 5 — `parallel`

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

### Primitive 6 — `loop`

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

## 6 Official Workflow Patterns

Claude Code's official [dynamic workflows](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) expose 6 workflow **design patterns** (Classify-and-act, Fan-out-and-synthesize, Adversarial verification, Generate-and-filter, Tournament, Loop until done) that Claude composes as JavaScript. CC Workflows implements each of these as a native CLI command — no JS workflow files required.

### Pattern 1 — `classify`

**Classify-and-act**: Use a classifier agent to decide the task type, then route to different agents/behaviors.

```bash
python3 claude_orchestrator.py classify \
  "Classify this bug report: security vulnerability or performance issue?" \
  --class-security "Run security audit, check CWE patterns, produce severity report" \
  --class-performance "Profile the code, identify bottlenecks, suggest optimizations" \
  --default "Run general bug analysis covering both aspects"
```

How it works:
1. Runs a classifier agent (`Explore` by default) on your classify prompt
2. Matches the output against your `--class-<key>` action prompts
3. Executes the matching action prompt with `general-purpose`
4. If no match, falls back to `--default`

### Pattern 2 — `fanout`

**Fan-out-and-synthesize**: Split a task into many smaller steps, run an agent on each, then synthesize results.

```bash
python3 claude_orchestrator.py fanout \
  "Analyze the codebase for security issues" \
  --subtask "Scan src/auth.py for auth bypasses" \
  --subtask "Scan src/api.py for injection flaws" \
  --subtask "Scan src/db.py for SQL injection" \
  --synthesize "Combine all findings into a prioritized security report with remediation steps"
```

How it works:
1. Each `--subtask` runs concurrently in its own git worktree (isolation)
2. All subtask outputs are collected
3. If `--synthesize` is provided, a final agent merges all results into one report
4. Worktrees are auto-merged and cleaned up by default (`--keep-worktree` to preserve)

### Pattern 3 — `verify`

**Adversarial verification**: Run a task, then spawn a separate verifier agent to adversarially check the output against a rubric. Repeat until PASS or max rounds reached.

```bash
python3 claude_orchestrator.py verify \
  "Implement a JWT authentication middleware for FastAPI" \
  --rubric "1. Must have unit tests covering success/failure cases
            2. Must validate token expiry
            3. Must handle malformed tokens gracefully
            4. Must follow project style guide (black, type hints)" \
  --verifier-agent Explore \
  --max-rounds 3
```

How it works:
1. Main agent executes the task
2. Verifier agent (`Explore` by default) scores the output against the rubric
3. If FAIL, the main agent gets the issues and produces a corrected version
4. Repeats up to `--max-rounds` times
5. Outputs the final (hopefully verified) result

### Pattern 4 — `genfilter`

**Generate-and-filter**: Generate N ideas/solutions, then filter them by a rubric, returning only the highest quality candidates.

```bash
python3 claude_orchestrator.py genfilter \
  "Generate 5 creative names for a CLI tool that manages dotfiles" \
  --count 5 \
  --rubric "Short (1-2 syllables), memorable, no common conflicts, available as npm package" \
  --filter-top 3
```

How it works:
1. Spawns `--count` parallel agents, each generating an independent solution
2. All results are fed to a judge agent with the rubric
3. Judge scores and ranks each solution
4. Top `--filter-top` results are returned with full details

### Pattern 5 — `tournament`

**Tournament**: Have N agents compete on the same task using different approaches, then a judge agent picks the winner.

```bash
python3 claude_orchestrator.py tournament \
  "Implement a thread-safe LRU cache in Python" \
  --contestants 3 \
  --judge "Best solution: correct thread safety, O(1) get/put, clean code, good tests"
```

How it works:
1. Spawns `--contestants` agents, each given a different "approach" framing (direct/robust/optimized/creative/standard)
2. All contestants run concurrently in isolated worktrees
3. A judge agent (`Explore`) evaluates all submissions pairwise against the task + judge prompt
4. Winner is announced with scoring breakdown

### Pattern 6 — `loop_until`

**Loop until done**: For tasks with an unknown amount of work, loop spawning agents until a stop condition is met (instead of a fixed number of passes).

```bash
python3 claude_orchestrator.py loop_until \
  "Investigate why the CI pipeline is failing and fix all issues" \
  --stop-condition "CI pipeline passes on the main branch" \
  --max-iterations 10
```

How it works:
1. Executes the task prompt in a loop (with session resume between iterations)
2. After each iteration, a lightweight checker agent evaluates whether the stop condition is MET
3. If MET → exit and show final output
4. If NOT_MET → continue to next iteration (up to `--max-iterations`)
5. State is persisted to `/tmp/claude_orchestrator_state.json`, survives restarts

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

  classify <prompt> [--class-KEY "action"] [--default "action"]   Classify-and-act
  fanout <prompt> [--subtask "X"] [--synthesize "Y"] [--agent Z]   Fan-out-and-synthesize
  verify <prompt> [--rubric "X"] [--verifier-agent Y] [--max-rounds N]   Adversarial verification
  genfilter <prompt> [--count N] [--rubric "X"] [--filter-top K]   Generate-and-filter
  tournament <prompt> [--contestants N] [--judge "X"]   Tournament
  loop_until <prompt> --stop-condition "X" [--max-iterations N]   Loop until done

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

CC Workflows integrates with Superpowers in two ways:

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
