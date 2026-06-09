---
name: claude-orchestrator
description: >
  A multi-agent dynamic workflow orchestrator for Claude Code. Provides 6 execution
  modes built on `claude -p`: single-agent runs, sequential pipelines, conditional
  branching, parallel task fan-out, long-horizon looped workflows, and session inspection.
  Automatically detects git root, isolates parallel tasks with worktrees, supports
  breakpoint-resume, and auto-injects Superpowers workflow constraints.
version: 2.0.0
---

# Claude Orchestrator

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Claude Code](https://img.shields.io/badge/Claude_Code-v2.1.168%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)

**A professional multi-agent workflow orchestrator for Claude Code.**

</div>

---

<!-- TOC -->
## Table of Contents

- [English](#english)
  - [Overview](#overview)
  - [Quick Start](#quick-start)
  - [Installation](#installation)
  - [6 Execution Modes](#6-execution-modes)
  - [CLI Reference](#cli-reference)
  - [Advanced Features](#advanced-features)
  - [Superpowers Integration](#superpowers-integration)
  - [Output Parsing](#output-parsing)
  - [Troubleshooting](#troubleshooting)
- [中文](#中文)
  - [概述](#概述)
  - [快速开始](#快速开始)
  - [安装](#安装)
  - [6 种执行模式](#6-种执行模式)
  - [CLI 参考](#cli-参考)
  - [高级功能](#高级功能)
  - [Superpowers 集成](#superpowers-集成)
  - [输出解析](#输出解析)
  - [故障排查](#故障排查)
- [License](#license)
<!-- /TOC -->

---

<!-- ENGLISH SECTION -->
<a name="english"></a>
## English

### Overview

Claude Orchestrator is a **production-grade** Python wrapper around `claude -p` (Claude Code's non-interactive headless mode). It turns one-off prompts into **repeatable, resumable, observable** workflows — without leaving your terminal.

<div align="center">

```
Single agent   →  run
Sequential     →  pipeline
Conditional    →  branch
Parallel       →  parallel  (with git worktree isolation)
Long loop      →  loop      (breakpoint-resume, up to 100 steps)
Inspect        →  sessions
```

</div>

### Quick Start

```bash
# 1. Install
python3 install.py

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

### Installation

#### Option A: `install.py` (recommended)

```bash
git clone https://github.com/<your-org>/claude-orchestrator.git
cd claude-orchestrator
python3 install.py
```

Copies the script to:
- `~/.hermes/skills/claude-orchestrator/claude_orchestrator.py` — Hermes Agent
- `~/.claude/skills/claude-orchestrator/claude_orchestrator.py` + `SKILL.md` — Claude Code

#### Option B: Claude Code plugin

```bash
# In your project root
mkdir -p .claude/skills/claude-orchestrator
cp claude_orchestrator.py .claude/skills/claude-orchestrator/
cp SKILL.md .claude/skills/claude-orchestrator/
```

Claude Code will auto-discover skills that contain a `SKILL.md` file.

#### Option C: Global Hermes Agent skill

```bash
mkdir -p ~/.hermes/skills/claude-orchestrator
cp claude_orchestrator.py ~/.hermes/skills/claude-orchestrator/
```

### 6 Execution Modes

#### Mode 1 — `agents`

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

#### Mode 2 — `run`

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

#### Mode 3 — `pipeline`

Run multiple steps **sequentially**, each step can use a different agent. Session is carried forward automatically.

```bash
python3 claude_orchestrator.py pipeline \
  --step "Explore: list all .py files under src/" --agent Explore \
  --step "Analyze: estimate cyclomatic complexity of each file" --agent general-purpose \
  --step "Plan: produce a refactor plan" --agent Plan
```

#### Mode 4 — `branch`

Sequential pipeline with **conditional branching**. After a designated evaluation step, the orchestrator jumps to either the `--then-step` or `--else-step`.

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

#### Mode 5 — `parallel`

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

#### Mode 6 — `loop`

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

#### `sessions`

Inspect active background Claude sessions and the orchestrator's own tracked state.

```bash
python3 claude_orchestrator.py sessions
```

### CLI Reference

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

### Advanced Features

#### Automatic Project Root Detection

The script runs `git rev-parse --show-toplevel` at startup. If the cwd is inside a git repo it uses that root; otherwise it falls back to `Path.cwd()`. No hardcoded paths.

#### State Persistence

All multi-step modes write to `/tmp/claude_orchestrator_state.json` after every step. If a run is killed (Ctrl-C, timeout, crash), re-running the same command resumes from the last completed step — zero data loss.

#### Superpowers Workflow Auto-Injection

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

#### `--interactive` Pre-flight (Loop Only)

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

#### Output Parsing

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

### Superpowers Integration

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

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| `claude: command not found` | Set the full path to the `claude` binary in `claude_orchestrator.py` (`cmd[0]`). Common path: `/Users/<user>/.local/bin/claude` |
| `EOFError` in `--interactive` | `--interactive` requires a TTY. Remove it; do clarification in the Claude Code conversation first |
| `result.result` is empty | Normal — the parser falls back to `assistant` event text blocks |
| Worktree merge conflict | The worktree is preserved at `/tmp/orchestrator-worktrees/orchestrator-<name>`. Resolve manually, then run `git merge --no-edit orchestrator-<name>` from your project root |
| State file grows large | Run `python3 claude_orchestrator.py loop "dummy" --max-steps 0` to reset (completes any pending loop and clears state) |

---

<!-- CHINESE SECTION -->
<a name="中文"></a>
## 中文

### 概述

Claude Orchestrator 是一个**生产级**的 Python 封装，底层调用 `claude -p`（Claude Code 的非交互无头模式）。它将一次性 prompt 转化为**可重复执行、断点续接、可观测**的工作流，全程在终端完成。

<div align="center">

```
单 agent 执行  →  run
顺序流水线    →  pipeline
条件分支      →  branch
并行派发      →  parallel（带 git worktree 隔离）
长任务循环    →  loop（断点续接，最多 100 段）
查看会话      →  sessions
```

</div>

### 快速开始

```bash
# 1. 安装
python3 install.py

# 2. 验证可用 agent
python3 ~/.hermes/skills/claude-orchestrator/claude_orchestrator.py agents

# 3. 单任务执行
python3 ~/.hermes/skills/claude-orchestrator/claude_orchestrator.py run \
  "重构 auth.py，添加类型提示" \
  --agent general-purpose

# 4. 长任务分段执行（自动断点续接）
python3 ~/.hermes/skills/claude-orchestrator/claude_orchestrator.py loop \
  "第 1 步: 列出 src/ 下所有 .py 文件
第 2 步: 读取 auth.py 并总结结构
第 3 步: 读取 api.py 并总结结构
第 4 步: 写一份涵盖两个文件的重构方案" \
  --max-steps 100
```

### 安装

#### 方式 A：`install.py`（推荐）

```bash
git clone https://github.com/<your-org>/claude-orchestrator.git
cd claude-orchestrator
python3 install.py
```

安装位置：
- `~/.hermes/skills/claude-orchestrator/claude_orchestrator.py` — Hermes Agent 用
- `~/.claude/skills/claude-orchestrator/claude_orchestrator.py` + `SKILL.md` — Claude Code 用

#### 方式 B：项目级 Claude Code skill

```bash
mkdir -p .claude/skills/claude-orchestrator
cp claude_orchestrator.py .claude/skills/claude-orchestrator/
cp SKILL.md .claude/skills/claude-orchestrator/
```

Claude Code 会自动发现包含 `SKILL.md` 的技能目录。

#### 方式 C：Hermes Agent 全局 skill

```bash
mkdir -p ~/.hermes/skills/claude-orchestrator
cp claude_orchestrator.py ~/.hermes/skills/claude-orchestrator/
```

### 6 种执行模式

#### 模式 1 — `agents`：查看可用 agent

不调用模型，30 秒内从 system init 事件读取所有可用 agent。

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

#### 模式 2 — `run`：单 agent 执行

执行单个 prompt，支持指定 agent 和 model。再次执行时自动续接上次会话。

```bash
python3 claude_orchestrator.py run "任务描述" --agent Explore
python3 claude_orchestrator.py run "任务描述" --agent Plan --model step-3.7-flash
```

输出：

```
✅ Step 1 | end_turn | 3 turns | $0.0123
🤖 Model: step-3.7-flash
<输出内容>
```

#### 模式 3 — `pipeline`：多 agent 流水线（顺序执行）

每一步可使用不同 agent，session 自动续接。

```bash
python3 claude_orchestrator.py pipeline \
  --step "Explore: 列出 src/ 下所有 .py 文件" --agent Explore \
  --step "Analyze: 评估每个文件的圈复杂度" --agent general-purpose \
  --step "Plan: 给出重构方案" --agent Plan
```

#### 模式 4 — `branch`：条件分支

在指定步骤评估条件，根据结果跳转到 `--then-step` 或 `--else-step`。

```bash
python3 claude_orchestrator.py branch \
  --step "扫描: 统计高危安全漏洞数量，输出 bugs_found = <数字>" --agent Explore \
  --step "报告: 总结发现" --agent general-purpose \
  --step "修复: 生成修复方案（漏洞数 > 0 时执行）" --agent general-purpose \
  --step "跳过: 记录无问题（漏洞数 = 0 时执行）" --agent general-purpose \
  --if "bugs_found > 0" --then-step 3 --else-step 4
```

条件语法：

| 语法 | 示例 |
|------|------|
| 数值比较 | `bugs_found > 0`, `count >= 5`, `severity == 3` |
| 字符串包含 | `output contains 'PASS'`, `result contains 'error'` |

#### 模式 5 — `parallel`：并行派发

最多 8 个任务同时执行，每个任务拥有独立的 session 和 **git worktree 隔离**。

```bash
python3 claude_orchestrator.py parallel \
  --task "分析 src/auth.py 并列出安全问题" --agent Explore --name auth \
  --task "分析 src/api.py 并列出安全问题" --agent Explore --name api \
  --task "分析 src/db.py 并列出安全问题" --agent Explore --name db
```

输出：

```
🔄 并行执行 3 个任务...
  🌳 [auth] worktree: /tmp/orchestrator-worktrees/orchestrator-auth
  🚀 [auth] 启动...
  🔗 [auth] 已合并到当前分支
  🧹 [auth] worktree 已清理

📊 并行结果:
  ✅ [auth] 4 turns, $0.0234
  ✅ [api]  3 turns, $0.0189
  ✅ [db]   5 turns, $0.0312
```

Worktree 行为控制：

| 参数 | 行为 |
|------|------|
| *(默认)* | 创建 worktree → 执行 → `git merge --no-edit` 合并 → 清理 worktree |
| `--keep-worktree` | 跳过合并和清理，worktree 保留在 `/tmp/orchestrator-worktrees/orchestrator-<name>` |
| `--no-worktree` | 关闭隔离，所有任务直接在共享项目目录执行 |

#### 模式 6 — `loop`：长任务自动循环

将 prompt 按换行拆成独立步骤，每步执行一次，自动续接。中断后重新运行会从上次停止的步骤继续。

```bash
python3 claude_orchestrator.py loop \
  "第 1 步: 列出所有 Python 文件
第 2 步: 读取 auth.py 并总结
第 3 步: 读取 api.py 并总结
第 4 步: 写重构方案" \
  --max-steps 100 \
  --agent Explore
```

断点续接示例：

```bash
# 第一次：最多 2 步
python3 claude_orchestrator.py loop "..." --max-steps 2
# → ⏸️ 本次执行 2 段完成，还剩 2 步未执行

# 第二次：同一条命令，从第 3 步继续
python3 claude_orchestrator.py loop "..." --max-steps 2
# → 🔄 从上次中断处继续，还剩 2 步... 第 3 步 → 第 4 步
```

状态保存在 `/tmp/claude_orchestrator_state.json`，进程重启不丢失。

#### `sessions`：查看会话状态

```bash
python3 claude_orchestrator.py sessions
```

### CLI 参考

```
python3 claude_orchestrator.py <命令> [选项]

命令:
  agents                                   查看可用 agent
  run <prompt> [--agent X] [--model Y]     单 agent 执行
  pipeline --step "X" --agent Y [...]      顺序多 agent 流水线
  branch  --step "X" --agent Y [...]       条件分支流水线
  parallel --task "X" --agent Y --name Z [...]  并行派发
  loop <prompt> [--max-steps N] [--agent X] [--interactive]  长任务循环
  sessions                                 查看会话状态

全局参数（自动注入）:
  --dangerously-skip-permissions           跳过权限确认
  --allowedTools Read,Write,Edit,Bash,Grep,Glob,TodoWrite
  --max-turns 12                           每段最大轮次
  --output-format json                     结构化事件流输出
```

### 高级功能

#### 自动检测项目根目录

启动时执行 `git rev-parse --show-toplevel`，若当前目录在 git 仓库内则使用该仓库根目录，否则回退到 `Path.cwd()`。无需硬编码路径。

#### 状态持久化

所有多步模式在每步执行后写入 `/tmp/claude_orchestrator_state.json`。即使进程被 kill（Ctrl-C、超时、崩溃），重新执行相同命令即可从上次完成的步骤继续，**零数据丢失**。

#### Superpowers 工作流自动注入

`loop` 模式会检测每步 prompt 中的关键词，自动在任务文本前注入对应的 [Superpowers](https://github.com/obra/superpowers) 约束。

| 关键词 | 注入的 skill |
|--------|-------------|
| `tdd`, `test-driven`, `测试驱动`, `红绿重构` | test-driven-development |
| `plan`, `规划`, `拆解`, `任务分解` | writing-plans |
| `subagent`, `并行`, `多 agent`, `派发` | subagent-driven-development |
| `review`, `评审`, `code review` | requesting-code-review |
| `debug`, `调试`, `修复 bug`, `排查` | systematic-debugging |
| 其他 | 通用工作流提醒 |

例如，单个 `loop` step：

```
用 TDD 重构 auth.py：先写失败测试，再写代码，再重构
```

会自动注入 Red-Green-Refactor 约束，无需手动编写复杂 prompt。

#### `--interactive` 预检（仅 loop 模式）

加 `--interactive` 在循环开始前触发一次 **Superpowers brainstorming 风格**的需求澄清：

1. 通过 `claude -p` 生成 2–3 个简短澄清问题
2. 收集用户回答（或输入 `skip` 跳过）
3. 生成精炼后的 prompt
4. 用精炼后的 prompt 进入正常分段循环

```
🔍 Superpowers brainstorming: 需求澄清
========================================

  Q1: "完成"的标准是什么？
  Q2: 哪些文件/模块在范围内？
  Q3: 有没有约束（TDD、code review、指定 agent）？

  A1: 所有测试必须通过
  A2: 仅限 src/auth.py
  A3: 遵循 TDD，需要 code review

📝 Refined prompt:
   用 TDD 重构 src/auth.py，所有测试通过后提交...
```

> **注意：** `--interactive` 需要真实 TTY。在非交互子进程（Claude Code 子 agent、CI 管道）中会报 `EOFError`。需求澄清应在 Claude Code 对话中完成，确认后再执行脚本。

#### 输出解析

Claude Code 的 `--output-format json` 输出中，`result.result` 字段经常为空字符串，实际文本内容在 preceding `assistant` 事件的 `message.content[].text` 块中。编排器的 `_parse_claude_output` 函数会按以下顺序提取：

```python
# 1. 尝试 result.result
output = last_result.get("result") or ""

# 2. 回退：拼接所有 assistant text 块
if not output.strip():
    text_parts = [
        block["text"]
        for e in events if e.get("type") == "assistant"
        for block in e.get("message", {}).get("content", [])
        if block.get("type") == "text"
    ]
    output = "\n".join(text_parts).strip()

# 3. model 字段：result.model 为空时从 modelUsage 取
model = last_result.get("model") or list(last_result.get("modelUsage", {}).keys())[0]
```

详见 [`references/output-parsing.md`](references/output-parsing.md)。

### Superpowers 集成

[Superpowers](https://github.com/obra/superpowers)（ obra 出品）是一套编码代理的最佳实践 skill 集，包含 TDD、subagent-driven-development、writing-plans、requesting-code-review、systematic-debugging、brainstorming 等。

Claude Orchestrator 通过两种方式与 Superpowers 集成：

1. **自动注入** — `loop` 模式检测到工作流关键词时，自动在每步前追加对应约束文本。
2. **手动组合** — 在 prompt 中使用 Superpowers 关键词：

```bash
# 通过自动注入强制 TDD
python3 claude_orchestrator.py loop \
  "实现用户注册功能，使用 TDD" \
  --max-steps 50

# 通过自动注入强制 subagent 驱动开发
python3 claude_orchestrator.py loop \
  "使用 subagent-driven-development 重构 auth 模块" \
  --max-steps 80
```

安装 Superpowers 插件：

```bash
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

### 故障排查

| 现象 | 解决方法 |
|------|---------|
| `claude: command not found` | 在脚本中设置 `claude` 的完整路径（常见路径：`/Users/<用户>/.local/bin/claude`） |
| `--interactive` 报 `EOFError` | `--interactive` 需要 TTY。去掉该参数，在 Claude Code 对话中先完成需求澄清 |
| `result.result` 为空 | 正常现象 — 解析器会自动回退到 `assistant` 事件的 text 块 |
| Worktree 合并冲突 | Worktree 保留在 `/tmp/orchestrator-worktrees/orchestrator-<name>`，手动解决后在项目根执行 `git merge --no-edit orchestrator-<name>` |
| 状态文件过大 | 执行 `python3 claude_orchestrator.py loop "dummy" --max-steps 0` 可重置状态（完成 pending loop 并清空） |

---

## License

[MIT](LICENSE) — feel free to use, modify, and distribute.
