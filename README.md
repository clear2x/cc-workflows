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
💬 > List available agents
💬 > Refactor auth.py and add type hints
💬 > Run a 50-step loop to refactor src/
💬 > Analyze these 3 files in parallel
```

Claude will automatically pick the right mode and execute it.

## Best Practices: Using in Claude Code

### Talk Naturally

You do not need to memorize mode names or command syntax. Just describe what you want in plain language inside Claude Code, and Claude will automatically pick the right mode for you. Here are some examples:

| What you say | Mode Claude picks |
|---|---|
| "Analyze these 3 files in parallel" | `parallel` |
| "Scan for issues first, fix if found" | `branch` |
| "Let 3 approaches compete, pick the best" | `tournament` |
| "Keep looping until tests pass" | `loop_until` |
| "Generate several options then filter for the best" | `genfilter` |
| "Classify this task, then route to the right agent" | `classify` |

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
💬 In Claude Code:
> List available agents
```

Output:

```
Available Agents:
  • Explore
  • Plan
  • general-purpose
  • claude
...
```

### `run`

Execute a single prompt with an optional agent, auto-resuming from the last session on re-run.

```
💬 In Claude Code:
> Read calculator.py and summarize its functionality

(Resume from last session)
> Now add modulo and power operations to it
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
💬 In Claude Code:
> Run a 3-step pipeline: find the largest .py file, summarize it, then suggest 3 optimizations
```

### `branch`

Sequential pipeline with **conditional branching**. After a designated evaluation step, the orchestrator jumps to either the `--then-step` or the `--else-step`.

```
💬 In Claude Code:
> Scan for security vulnerabilities — if found, generate a fix plan; if not, log "no issues"
```

Supported condition syntax:

| Syntax | Example |
|--------|---------|
| Numeric comparison | `bugs_found > 0`, `count >= 5`, `severity == 3` |
| String contains | `output contains 'PASS'`, `result contains 'error'` |

### `parallel`

Run multiple tasks **concurrently** (up to 8 workers). Each task gets its own session and an isolated **git worktree**. By default the script **auto-merges** each branch back and cleans the worktree when the task finishes.

```
💬 In Claude Code:
> Analyze 3 files in parallel: auth.py for security, api.py for performance, db.py for structure
```

Output:

```
🔄 Running 3 tasks in parallel...
  🌳 [auth] worktree: /tmp/orchestrator-worktrees/orchestrator-auth
  🚀 [auth] Starting...
  🔗 [auth] Merged to current branch
  🧹 [auth] Worktree cleaned up

📊 Parallel results:
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
💬 In Claude Code:
> Run a 4-step loop: list files → find the largest → summarize it → suggest optimizations

(Breakpoint resume)
> Run the same 4-step task, but limit to 2 steps first, then resume the rest
```

Breakpoint-resume behaviour:

- First run: 2 steps → ⏸️ Completed 2 segments, 2 steps remaining
- Second run: same prompt → 🔄 Resuming from where it stopped, 2 steps remaining... Step 3 → Step 4

State is stored at `/tmp/claude_orchestrator_state.json` and survives process restarts.

### `sessions`

Inspect active background Claude sessions and the orchestrator's own tracked state.

```
💬 In Claude Code:
> Show active sessions
```

## Workflow Patterns

### `classify`

**Classify-and-act**: Use a classifier agent to decide the task type, then route to different agents/behaviors.

```
💬 In Claude Code:
> Classify the risk in this SQL: SELECT * FROM users WHERE id = user_input — route as security or performance
```

How it works:
1. Runs a classifier agent (`Explore` by default) on your classify prompt
2. Matches the output against your `--class-<key>` action prompts
3. Executes the matching action prompt with `general-purpose`
4. If no match, falls back to `--default`

### `fanout`

**Fan-out-and-synthesize**: Split a task into many smaller steps, run an agent on each, then synthesize results.

```
💬 In Claude Code:
> Fan-out: review auth.py security, review api.py scalability, check README completeness — then synthesize into one report
```

How it works:
1. Each `--subtask` runs concurrently in its own git worktree (isolation)
2. All subtask outputs are collected
3. If `--synthesize` is provided, a final agent merges all results into one report
4. Worktrees are auto-merged and cleaned up by default (`--keep-worktree` to preserve)

### `verify`

**Adversarial verification**: Run a task, then spawn a separate verifier agent to adversarially check the output against a rubric. Repeat until PASS or max rounds reached.

```
💬 In Claude Code:
> Verify: write a Fibonacci function, then check it has function definition, boundary handling, and complexity note — max 2 rounds
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
💬 In Claude Code:
> Generate 3 creative names for this project — criteria: short, memorable, tech feel — return the best 1
```

How it works:
1. Spawns `--count` parallel agents, each generating an independent solution
2. All results are fed to a judge agent with the rubric
3. Judge scores and ranks each solution
4. Top `--filter-top` results are returned with full details

### `tournament`

**Tournament**: Have N agents compete on the same task using different approaches, then a judge agent picks the winner.

```
💬 In Claude Code:
> Tournament: 3 contestants compete to "explain recursion in one sentence" — judge on accuracy, clarity, brevity
```

How it works:
1. Spawns `--contestants` agents, each given a different "approach" framing (direct/robust/optimized/creative/standard)
2. All contestants run concurrently in isolated worktrees
3. A judge agent (`Explore`) evaluates all submissions pairwise against the task + judge prompt
4. Winner is announced with scoring breakdown

### `loop_until`

**Loop until done**: For tasks with an unknown amount of work, loop spawning agents until a stop condition is met (instead of a fixed number of passes).

```
💬 In Claude Code:
> Loop until calculator.py has sqrt, abs, and round functions — max 5 iterations
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
  progress                             Check progress of running task

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

### Progress Feedback During Execution

CC Workflows supports **two execution forms** for real-time progress feedback, both fully supported:

#### Form 1: Native Workflow Tool Orchestration

When you trigger a cc-workflows pattern, Claude uses the Workflow tool to orchestrate it — you see phases and agents update in real-time:

```
💬 > Analyze these 3 files in parallel

You see in real-time:
  ▸ Parallel Analysis (3 agents)
    ✅ agent:auth — Analyze auth.py security
    ✅ agent:api — Analyze api.py performance
    ✅ agent:db — Analyze db.py structure
```

Mode mapping:

| cc-workflows mode | Workflow tool implementation |
|-------------------|------------------------------|
| `parallel` | `parallel()` + `agent()` per task |
| `pipeline` | `pipeline()` with multiple stages |
| `verify` | `agent(exec)` → `agent(verify)` loop |
| `fanout` | `parallel()` subtasks → `agent()` synthesize |
| `tournament` | `parallel()` compete → `agent()` judge |
| `classify` | `agent(classify)` → `agent(route)` |

#### Form 2: cc_workflows.py + Progress Polling

Use cc_workflows.py subprocess with background execution and progress file polling. **Best for:** long tasks (> 20 steps), breakpoint resume, Superpowers auto-injection, batch parallel (> 8 tasks).

```
💬 > Refactor auth.py in 7 steps, max 50 steps

Claude: Running in background, I'll report progress periodically.

[30s later]
📊 Progress: 3/7 steps | 💰 $0.12

[Task completes]
🎉 All 7 steps done! 25 total turns, $0.34
```

#### Decision Guide

| Condition | Execution method |
|-----------|-----------------|
| User specifies preference | Follow user's choice |
| Default (most tasks) | Native Workflow tool |
| Task > 20 steps | cc_workflows.py background |
| Need breakpoint resume | cc_workflows.py background |
| Need Superpowers auto-injection | cc_workflows.py loop |
| Batch parallel > 8 tasks | cc_workflows.py background |

### Automatic Project Root Detection

The script runs `git rev-parse --show-toplevel` at startup. If the cwd is inside a git repo it uses that root; otherwise it falls back to `Path.cwd()`. No hardcoded paths.

### State Persistence

All multi-step modes write to `/tmp/claude_orchestrator_state.json` after every step. If a run is killed (Ctrl-C, timeout, crash), re-running the same command resumes from the last completed step — zero data loss.

### Superpowers Workflow Auto-Injection

The `loop` mode inspects each step's prompt for keywords and automatically injects the matching [Superpowers](https://github.com/obra/superpowers) constraint before the actual task text.

| Keyword pattern | Injected skill |
|-----------------|----------------|
| `tdd`, `test-driven` | test-driven-development |
| `plan`, `decompose` | writing-plans |
| `subagent`, `multi-agent` | subagent-driven-development |
| `review`, `code review` | requesting-code-review |
| `debug`, `fix bug` | systematic-debugging |
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
💬 In Claude Code:
> Run a 50-step loop to implement user registration using TDD

> Run an 80-step loop to refactor the auth module using subagent-driven-development
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
💬 In Claude Code:
> /cc-workflows Refactor the auth module to add OAuth2 support

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
💬 In Claude Code:
> /cc-workflows loop Refactor auth.py with TDD, 7 steps:
> Step 1: Write failing OAuth2 tests for auth.py using TDD
> Step 2: Implement minimal code to pass tests
> Step 3: Refactor — extract shared logic
> Step 4: Write failing token refresh tests using TDD
> Step 5: Implement refresh logic
> Step 6: Run full test suite — confirm no regressions
> Step 7: Commit code
> Max 50 steps
```

**Why this works:**
- `loop` auto-detects keywords (e.g., `TDD`, `test`) and injects Superpowers constraints
- Each segment clears context via `--resume`, preventing overflow
- Supports breakpoint resume — just say "continue" to pick up where it left off

### Practice 3: Parallel Exploration → cc-workflows `parallel` + Explore Agent

When you need to **analyze multiple independent subsystems simultaneously**:

```
💬 In Claude Code:
> /cc-workflows parallel Analyze 3 dimensions:
> Dimension 1: Audit auth.py security (SQL injection, XSS, privilege escalation)
> Dimension 2: Profile api.py performance (N+1 queries, missing cache, slow queries)
> Dimension 3: Check db.py data integrity (missing constraints, race conditions, migration issues)
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
💬 In Claude Code:
> /cc-workflows verify Implement a JWT middleware with token validation, refresh, and blacklist.
> Rubric: 1. Unit tests covering normal and error paths 2. Token expiry validation 3. Malformed token handling 4. Follow project style
> Max 3 verification rounds
```

**This is equivalent to Superpowers' spec review + code quality review, but executed through cc-workflows' isolated subprocess.**

### Practice 5: Solution Selection → `tournament` / `genfilter`

**Competing approaches** (mirrors Superpowers brainstorming's "propose 2-3 approaches"):

```
💬 In Claude Code:
> /cc-workflows tournament 3 contestants compete to "implement a thread-safe LRU cache",
> judge on "correct thread safety, O(1) read/write, clean code, good tests"

> /cc-workflows genfilter Design 3 error handling schemes for a REST API,
> criteria: unified format, error codes, i18n support — return the best 1
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
