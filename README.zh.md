# CC Workflows

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Claude Code](https://img.shields.io/badge/Claude_Code-v2.1.168%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)

**一个专业级多 Agent 工作流调度器，专为 Claude Code 设计。**

</div>

[English](./README.md) | [中文](./README.zh.md)

---

## 目录

- [概述](#概述)
- [快速开始](#快速开始)
- [在 Claude Code 中使用](#在-claude-code-中使用)
  - [自然语言触发](#自然语言触发)
  - [斜杠命令](#斜杠命令)
  - [模式选择指南](#模式选择指南)
- [安装](#安装)
- [CLI 原语](#cli-原语)
  - [`agents`](#agents)
  - [`run`](#run)
  - [`pipeline`](#pipeline)
  - [`branch`](#branch)
  - [`parallel`](#parallel)
  - [`loop`](#loop)
  - [`sessions`](#sessions)
- [Workflow Pattern 模式](#workflow-pattern-模式)
  - [`classify`](#classify)
  - [`fanout`](#fanout)
  - [`verify`](#verify)
  - [`genfilter`](#genfilter)
  - [`tournament`](#tournament)
  - [`loop_until`](#loop_until)
- [CLI 参考](#cli-参考)
- [高级功能](#高级功能)
- [Superpowers 集成](#superpowers-集成)
- [最佳实践：cc-workflows × Superpowers](#最佳实践cc-workflows--superpowers)
- [输出解析](#输出解析)
- [故障排查](#故障排查)
- [开源协议](#开源协议)

---

<a name="概述"></a>
## 概述

CC Workflows 是一个**生产级**的 Python 封装，底层调用 `claude -p`（Claude Code 的非交互无头模式）。它将一次性 prompt 转化为**可重复执行、断点续接、可观测**的工作流，全程在终端完成。

### 12 种执行模式一览

| 模式 | 类型 | 说明 |
|------|------|------|
| `run` | CLI 原语 | 单 agent 执行，自动续接 |
| `pipeline` | CLI 原语 | 顺序多 agent 流水线 |
| `branch` | CLI 原语 | 条件分支流水线 |
| `parallel` | CLI 原语 | 并行派发，带 git worktree 隔离 |
| `loop` | CLI 原语 | 长任务分段循环，支持断点续接 |
| `sessions` | CLI 原语 | 查看活跃 Claude 会话 |
| `classify` | Workflow Pattern | 分类路由（Classify-and-act） |
| `fanout` | Workflow Pattern | 扇出聚合（Fan-out-and-synthesize） |
| `verify` | Workflow Pattern | 对抗验证（Adversarial verification） |
| `genfilter` | Workflow Pattern | 生成过滤（Generate-and-filter） |
| `tournament` | Workflow Pattern | 锦标赛（Tournament） |
| `loop_until` | Workflow Pattern | 条件循环（Loop until done） |

### 快速开始

```bash
# 1. 安装（一条命令）
npx skills add https://github.com/clear2x/cc-workflows

# 或安装单个模式技能：
# npx skills add https://github.com/clear2x/cc-workflows --skill cc-run

# 2. 验证可用 agent
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py agents

# 3. 单任务执行
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py run \
  "重构 auth.py，添加类型提示" \
  --agent general-purpose

# 4. 长任务分段执行（自动断点续接）
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop \
  "第 1 步: 列出 src/ 下所有 .py 文件
第 2 步: 读取 auth.py 并总结结构
第 3 步: 读取 api.py 并总结结构
第 4 步: 写一份涵盖两个文件的重构方案" \
  --max-steps 100
```

## 在 Claude Code 中使用

CC Workflows 以技能（skill）形式集成到 Claude Code 中。你可以通过**自然语言描述**或**斜杠命令**两种方式触发不同的工作流模式。

### 自然语言触发

在 Claude Code 对话中，直接描述你想要的工作方式，Claude 会自动选择合适的模式执行。无需记忆命令语法——说出你的意图就够了。

| 你说的话 | 触发的模式 |
|---------|-----------|
| "帮我并行分析这 3 个文件" | `parallel` |
| "先扫描有没有问题，有的话修复" | `branch` |
| "让 3 个方案竞争选出最好的" | `tournament` |
| "循环执行直到测试通过" | `loop_until` |
| "生成几个方案然后筛选最好的" | `genfilter` |
| "帮我跑一个 50 步的长任务" | `loop` |

### 斜杠命令

所有 13 个斜杠命令均可在 Claude Code 对话中直接使用：

| 命令 | 说明 |
|------|------|
| `/cc-workflows` | 查看所有模式 |
| `/cc-agents` | 查看可用 agent |
| `/cc-run` | 单任务执行 |
| `/cc-pipeline` | 顺序流水线 |
| `/cc-branch` | 条件分支 |
| `/cc-parallel` | 并行执行 |
| `/cc-loop` | 长任务循环 |
| `/cc-classify` | 分类路由 |
| `/cc-fanout` | 扇出聚合 |
| `/cc-verify` | 对抗验证 |
| `/cc-genfilter` | 生成过滤 |
| `/cc-tournament` | 锦标赛 |
| `/cc-loop-until` | 条件循环 |

### 模式选择指南

根据任务场景快速选择最合适的模式：

| 任务场景 | 推荐模式 |
|----------|---------|
| 单个任务 | `run` |
| 多步顺序执行 | `pipeline` |
| 根据条件选择执行 | `branch` |
| 多个任务同时执行 | `parallel` |
| 长任务分多步 | `loop` |
| 按类型分派 | `classify` |
| 并行+汇总 | `fanout` |
| 执行+质量检查 | `verify` |
| 生成多个方案选最优 | `genfilter` |
| 多方案竞争 | `tournament` |
| 循环直到达成目标 | `loop_until` |

## 安装

### 方式 A：`npx skills add`（推荐）

```bash
npx skills add https://github.com/clear2x/cc-workflows

# 或安装单个模式技能：
# npx skills add https://github.com/clear2x/cc-workflows --skill cc-run
```

会自动将所有模式技能（cc-run, cc-pipeline, cc-loop 等）复制到本地技能目录。

### 方式 B：`install.py`

```bash
git clone https://github.com/clear2x/cc-workflows.git
cd cc-workflows
python3 install.py
```

安装位置：
- `~/.hermes/skills/cc-workflows/cc_workflows.py` — 核心脚本（Hermes Agent 用）
- `~/.claude/skills/cc-workflows/cc_workflows.py` + `SKILL.md` — 核心脚本（Claude Code 用）

### 方式 C：手动复制

```bash
# Claude Code 项目级
mkdir -p .claude/skills/cc-workflows
cp skills/cc-workflows/cc_workflows.py .claude/skills/cc-workflows/
cp skills/cc-workflows/SKILL.md .claude/skills/cc-workflows/
```

```bash
# Hermes Agent 全局
mkdir -p ~/.hermes/skills/cc-workflows
cp skills/cc-workflows/cc_workflows.py ~/.hermes/skills/cc-workflows/
```

## 12 种执行模式

### `agents`：查看可用 agent

不调用模型，30 秒内从 system init 事件读取所有可用 agent。

```
💬 在 Claude Code 中：
> 用 cc-workflows 帮我看看有哪些可用的 agent
```

```bash
python3 cc_workflows.py agents
```

```
可用 Agents:
  • Explore
  • Plan
  • general-purpose
  • claude
...
```

### `run`：单 agent 执行

执行单个 prompt，支持指定 agent 和 model。再次执行时自动续接上次会话。

```
💬 在 Claude Code 中：
> 用 cc-workflows 的 run 模式，让 Explore agent 读一下 calculator.py 并总结功能

（续接上次会话）
> 再让它在刚才的基础上给 calculator.py 加上取模和幂运算
```

```bash
python3 cc_workflows.py run "任务描述" --agent Explore
python3 cc_workflows.py run "任务描述" --agent Plan --model step-3.7-flash
```

输出：

```
✅ Step 1 | end_turn | 3 turns | $0.0123
🤖 Model: step-3.7-flash
<输出内容>
```

### `pipeline`：多 agent 流水线（顺序执行）

每一步可使用不同 agent，session 自动续接。

```
💬 在 Claude Code 中：
> 用 cc-workflows pipeline 跑 3 步流水线：第1步扫描所有 .py 文件，第2步分析代码质量，第3步给出改进建议
```

```bash
python3 cc_workflows.py pipeline \
  --step "Explore: 列出 src/ 下所有 .py 文件" --agent Explore \
  --step "Analyze: 评估每个文件的圈复杂度" --agent general-purpose \
  --step "Plan: 给出重构方案" --agent Plan
```

### `branch`：条件分支

在指定步骤评估条件，根据结果跳转到 `--then-step` 或 `--else-step`。

```
💬 在 Claude Code 中：
> 用 cc-workflows 的 branch 模式：扫描有没有包含 TODO 注释的文件，有的话列出具体位置，没有的话说"无待办"
```

```bash
python3 cc_workflows.py branch \
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

### `parallel`：并行派发

最多 8 个任务同时执行，每个任务拥有独立的 session 和 **git worktree 隔离**。

```
💬 在 Claude Code 中：
> 用 cc-workflows 并行分析 3 个文件：calculator.py 的功能、logger.py 的功能、README.md 的内容
```

```bash
python3 cc_workflows.py parallel \
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

### `loop`：长任务自动循环

将 prompt 按换行拆成独立步骤，每步执行一次，自动续接。中断后重新运行会从上次停止的步骤继续。

```
💬 在 Claude Code 中：
> 用 cc-workflows loop 分 4 步执行：第1步列出所有文件，第2步读取 calculator.py，第3步读取 logger.py，第4步总结项目

（断点续接）
> 用 cc-workflows loop 跑 4 步任务，先限制只跑 2 步，然后再续接跑完
```

```bash
python3 cc_workflows.py loop \
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
python3 cc_workflows.py loop "..." --max-steps 2
# → ⏸️ 本次执行 2 段完成，还剩 2 步未执行

# 第二次：同一条命令，从第 3 步继续
python3 cc_workflows.py loop "..." --max-steps 2
# → 🔄 从上次中断处继续，还剩 2 步... 第 3 步 → 第 4 步
```

状态保存在 `/tmp/claude_orchestrator_state.json`，进程重启不丢失。

### `sessions`：查看会话状态

```
💬 在 Claude Code 中：
> 用 cc-workflows 查看当前活跃的会话状态
```

```bash
python3 cc_workflows.py sessions
```

## Workflow Pattern 模式

6 种高级工作流模式，每种模式解决一类特定的编排问题，全部实现为原生 CLI 命令，直接调用即可。

### `classify`（Classify-and-act）

先用一个 classifier agent 对任务进行分类，再根据分类结果路由到不同的 agent/行为。

```
💬 在 Claude Code 中：
> 用 cc-workflows classify 来分类这个任务："calculator.py 的 divide 函数除以零会怎样"，按 security 和 performance 分类处理
```

```bash
python3 cc_workflows.py classify \
  "Classify this bug: security vulnerability or performance issue?" \
  --class-security "Run security audit, check CWE patterns, produce severity report" \
  --class-performance "Profile the code, identify bottlenecks, suggest optimizations" \
  --default "Run general bug analysis covering both aspects"
```

执行流程：
1. 使用 classifier agent（默认 `Explore`）对 classify prompt 进行分析
2. 将输出与 `--class-<key>` 对应的 action prompt 进行匹配
3. 执行匹配到的 action prompt（使用 `general-purpose`）
4. 无匹配时回退到 `--default`

### `fanout`（Fan-out-and-synthesize）

将任务拆分为多个小步骤，每个步骤由独立的 agent 并发执行，最后汇总所有结果。

```
💬 在 Claude Code 中：
> 用 cc-workflows fanout 并行做 3 件事：审查 calculator.py 的安全性、审查 logger.py 的可扩展性、检查 README.md 是否完整，然后汇总成一份综合报告
```

```bash
python3 cc_workflows.py fanout \
  "Analyze the codebase for security issues" \
  --subtask "Scan src/auth.py for auth bypasses" \
  --subtask "Scan src/api.py for injection flaws" \
  --subtask "Scan src/db.py for SQL injection" \
  --synthesize "Combine all findings into a prioritized security report"
```

执行流程：
1. 每个 `--subtask` 在独立的 git worktree 中并发执行（隔离性好）
2. 收集所有子任务输出
3. 如果提供 `--synthesize`，最终 agent 会将所有结果合并为一份报告
4. 默认自动合并并清理 worktree（`--keep-worktree` 可保留）

### `verify`（Adversarial verification）

执行任务，然后由独立的 verifier agent 根据 rubric 对抗式地检查输出质量，不合格则自动修复，循环至通过或达到最大轮数。

```
💬 在 Claude Code 中：
> 用 cc-workflows verify 让它给 calculator.py 补充单元测试，验证标准是：覆盖加减乘除、有边界测试、有异常处理，最多验证 2 轮
```

```bash
python3 cc_workflows.py verify \
  "Implement a JWT authentication middleware for FastAPI" \
  --rubric "1. Must have unit tests covering success/failure cases
            2. Must validate token expiry
            3. Must handle malformed tokens gracefully
            4. Must follow project style guide (black, type hints)" \
  --verifier-agent Explore \
  --max-rounds 3
```

执行流程：
1. 主 agent 执行任务
2. verifier agent（默认 `Explore`）根据 rubric 评分
3. 如果 FAIL，主 agent 获得问题列表并生成修正版本
4. 循环最多 `--max-rounds` 次
5. 输出最终（ hopefully verified）结果

### `genfilter`（Generate-and-filter）

生成 N 个方案，再用 rubric 进行评分筛选，只返回质量最高的 K 个候选。

```
💬 在 Claude Code 中：
> 用 cc-workflows genfilter 给这个项目起 3 个名字，标准是简短好记体现功能，筛出最好的 1 个
```

```bash
python3 cc_workflows.py genfilter \
  "Generate 5 creative names for a CLI tool that manages dotfiles" \
  --count 5 \
  --rubric "Short (1-2 syllables), memorable, no common conflicts, available as npm package" \
  --filter-top 3
```

执行流程：
1. 并发启动 `--count` 个 agent，每个独立生成一个方案
2. 所有结果送入 judge agent 按 rubric 评分
3. Judge 对每个方案打分并排序
4. 返回 `--filter-top` 个最佳方案（含完整内容）

### `tournament`（Tournament）

N 个 agent 使用不同方法竞争同一个任务，由 judge agent pairwise 评比选出最终赢家。

```
💬 在 Claude Code 中：
> 用 cc-workflows tournament 让 3 个选手竞争"用最优雅的方式给 calculator.py 加上历史记录功能"，judge 按代码简洁性、可维护性、完整性评分
```

```bash
python3 cc_workflows.py tournament \
  "Implement a thread-safe LRU cache in Python" \
  --contestants 3 \
  --judge "Best solution: correct thread safety, O(1) get/put, clean code, good tests"
```

执行流程：
1. 启动 `--contestants` 个 agent，每个采用不同的 "approach" 风格（direct / robust / optimized / creative / standard）
2. 所有参赛者并发执行，使用独立 worktree 隔离
3. judge agent（`Explore`）根据任务要求和 judge prompt 对全部提交进行 pairwise 评估
4. 宣布获胜者，附上评分 breakdown

### `loop_until`（Loop until done）

对工作量不确定的任务，循环执行直到满足停止条件（而非固定次数）。

```
💬 在 Claude Code 中：
> 用 cc-workflows loop_until 让它给 calculator.py 添加功能，每轮加一个，直到包含了 sqrt、abs、round 三个函数为止，最多试 5 轮
```

```bash
python3 cc_workflows.py loop_until \
  "Investigate why the CI pipeline is failing and fix all issues" \
  --stop-condition "CI pipeline passes on the main branch" \
  --max-iterations 10
```

执行流程：
1. 在循环中执行任务 prompt（迭代间恢复 session）
2. 每轮结束后，轻量级 checker agent 评估停止条件是否 MET
3. MET → 退出并显示最终输出
4. NOT_MET → 继续下一轮（最多 `--max-iterations` 次）
5. 状态持久化到 `/tmp/claude_orchestrator_state.json`，支持重启续接

## CLI 参考

```
python3 cc_workflows.py <命令> [选项]

命令:
  agents                                   查看可用 agent
  run <prompt> [--agent X] [--model Y]     单 agent 执行
  pipeline --step "X" --agent Y [...]      顺序多 agent 流水线
  branch  --step "X" --agent Y [...]       条件分支流水线
  parallel --task "X" --agent Y --name Z [...]  并行派发
  loop <prompt> [--max-steps N] [--agent X] [--interactive]  长任务循环
  sessions                                 查看会话状态
  classify <prompt> [--class-KEY "action"] [--default "action"]  分类路由
  fanout <prompt> [--subtask "X"] [--synthesize "Y"] [--agent Z]  并发派发+汇总
  verify <prompt> [--rubric "X"] [--verifier-agent Y] [--max-rounds N]  对抗式验证
  genfilter <prompt> [--count N] [--rubric "X"] [--filter-top K]  生成+筛选
  tournament <prompt> [--contestants N] [--judge "X"]  锦标赛模式
  loop_until <prompt> --stop-condition "X" [--max-iterations N]  条件循环

全局参数（自动注入）:
  --dangerously-skip-permissions           跳过权限确认
  --allowedTools Read,Write,Edit,Bash,Grep,Glob,TodoWrite
  --max-turns 12                           每段最大轮次
  --output-format json                     结构化事件流输出
```

## 高级功能

### 自动检测项目根目录

启动时执行 `git rev-parse --show-toplevel`，若当前目录在 git 仓库内则使用该仓库根目录，否则回退到 `Path.cwd()`。无需硬编码路径。

### 状态持久化

所有多步模式在每步执行后写入 `/tmp/claude_orchestrator_state.json`。即使进程被 kill（Ctrl-C、超时、崩溃），重新执行相同命令即可从上次完成的步骤继续，**零数据丢失**。

### Superpowers 工作流自动注入

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

### `--interactive` 预检（仅 loop 模式）

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

## Superpowers 集成

[Superpowers](https://github.com/obra/superpowers)（ obra 出品）是一套编码代理的最佳实践 skill 集，包含 TDD、subagent-driven-development、writing-plans、requesting-code-review、systematic-debugging、brainstorming 等。

CC Workflows 通过两种方式与 Superpowers 集成：

1. **自动注入** — `loop` 模式检测到工作流关键词时，自动在每步前追加对应约束文本。
2. **手动组合** — 在 prompt 中使用 Superpowers 关键词：

```bash
# 通过自动注入强制 TDD
python3 cc_workflows.py loop \
  "实现用户注册功能，使用 TDD" \
  --max-steps 50

# 通过自动注入强制 subagent 驱动开发
python3 cc_workflows.py loop \
  "使用 subagent-driven-development 重构 auth 模块" \
  --max-steps 80
```

安装 Superpowers 插件：

```bash
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

## 最佳实践：cc-workflows × Superpowers

### 核心理解：分工与互补

| 维度 | Superpowers | cc-workflows |
|------|-------------|-------------|
| **角色** | 方法论（做什么、怎么做才对） | 执行引擎（怎么跑、怎么调度） |
| **关注点** | TDD 红绿循环、review 质量、计划规范 | 多 agent 并行、断点续接、长任务编排 |
| **执行环境** | Claude Code 主会话内（Agent tool / 子代理） | `claude -p` 子进程（独立 session） |
| **上下文** | 继承主会话，可交互式追问 | 隔离上下文，一次性 prompt |

**关键原则：Superpowers 决定"做什么"，cc-workflows 决定"怎么跑"。**

### 最佳实践一：对话内自然语言触发（推荐）

在 Claude Code 对话里，**不需要手动拼命令**。用自然语言描述需求，Claude 会自动：
1. 加载相关 superpowers skill（brainstorming → writing-plans → subagent-driven-development）
2. 选择合适的 cc-workflows 模式执行

**典型对话流程：**

```
你：我想给 auth 模块加 OAuth2 支持

Claude：
  → 自动触发 brainstorming skill
  → 逐个问题澄清需求
  → 提出 2-3 种方案
  → 你确认后写 spec
  → 触发 writing-plans skill
  → 生成详细的分步计划
  → 询问执行方式

你：用 subagent-driven-development 执行

Claude：
  → 自动触发 subagent-driven-development skill
  → 每个任务派独立子代理
  → spec review → code quality review
  → 所有任务完成后用 finishing-a-development-branch 收尾
```

**这个流程全程在对话内完成，不需要手动调 cc-workflows 命令。** Superpowers 的子代理机制已经内置了并行和隔离。

### 最佳实践二：长任务用 cc-workflows `loop` 跑 Superpowers 约束

当任务**超过 12 轮工具调用**或**需要 20+ 步**时，主会话上下文会溢出。这时用 cc-workflows loop：

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop \
  "Step 1: 用 TDD 方式为 auth.py 写 OAuth2 的失败测试
Step 2: 实现最小代码让测试通过
Step 3: 重构，提取公共逻辑
Step 4: 用 TDD 为 token 刷新写失败测试
Step 5: 实现刷新逻辑
Step 6: 运行全量测试确认无回归
Step 7: 提交代码" \
  --max-steps 50
```

**为什么这有效：**
- loop 模式会自动检测关键词（如 `TDD`、`测试`）并注入 superpowers 约束
- 每段执行完靠 `--resume` 清空上下文，避免溢出
- 支持断点续接，中断后重跑同一命令自动继续

### 最佳实践三：并行探索用 cc-workflows `parallel` + Explore agent

当需要**同时分析多个独立子系统**时：

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py parallel \
  --task "审查 auth.py 的安全性：检查 SQL 注入、XSS、权限绕过" --agent Explore --name security \
  --task "分析 api.py 的性能瓶颈：N+1 查询、缺少缓存、慢查询" --agent Explore --name perf \
  --task "检查 db.py 的数据完整性：约束缺失、竞态条件、迁移问题" --agent Explore --name data
```

**适用场景：**
- 代码审查（安全/性能/可维护性多维度并行）
- 多文件独立重构
- 多模块同时调试

**不适用场景：**
- 任务之间有依赖（改 A 会影响 B）
- 需要全局理解（一个 agent 看不全貌）

### 最佳实践四：验证闭环用 cc-workflows `verify`

**先实现，再对抗验证**——对应 superpowers 的 `verification-before-completion` 理念：

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py verify \
  "实现一个 JWT 中间件，支持 token 验证、刷新、黑名单" \
  --rubric "1. 必须有单元测试覆盖正常和异常路径
            2. 必须验证 token 过期
            3. 必须处理畸形 token
            4. 必须遵循项目风格（black, type hints）" \
  --max-rounds 3
```

**这等价于 superpowers 的 spec review + code quality review，但是通过 cc-workflows 的 `claude -p` 隔离执行。**

### 最佳实践五：方案选优用 `tournament` / `genfilter`

**多方案竞争**（对应 superpowers brainstorming 的"提出 2-3 种方案"）：

```bash
# tournament：N 个选手竞争，judge 选赢家
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py tournament \
  "实现一个线程安全的 LRU 缓存" \
  --contestants 3 \
  --judge "最优标准：线程安全正确、O(1) 读写、代码简洁、测试充分"

# genfilter：生成 N 个方案，按 rubric 筛选最好的 K 个
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py genfilter \
  "为 REST API 设计错误处理方案" \
  --count 3 --rubric "统一格式、包含错误码、支持国际化" --filter-top 1
```

### 决策树：什么时候用哪个

```
有需求？
├─ 需求不明确 → Superpowers brainstorming（对话内）
├─ 需求明确，要规划 → Superpowers writing-plans（对话内）
├─ 有计划，要执行
│   ├─ 任务 < 12 轮 → Superpowers subagent-driven-development（对话内 Agent tool）
│   ├─ 任务 > 12 轮 → cc-workflows loop（后台跑）
│   ├─ 多任务并行 → cc-workflows parallel 或 fanout
│   └─ 需要验证 → cc-workflows verify
├─ 方案选优 → cc-workflows tournament 或 genfilter
├─ 循环直到完成 → cc-workflows loop_until
└─ 不确定走哪条路 → cc-workflows classify
```

### 推荐组合速查表

| 场景 | Superpowers Skill | cc-workflows 模式 | 触发方式 |
|------|------------------|-------------------|---------|
| 探索需求 | brainstorming | — | 对话内自然语言 |
| 制定计划 | writing-plans | — | 对话内自然语言 |
| 小任务实现 | subagent-driven-development | — | 对话内或 `/cc-run` |
| 长任务 TDD | test-driven-development | `loop` | `/cc-loop` + TDD 关键词自动注入 |
| 多文件并行分析 | dispatching-parallel-agents | `parallel` | `/cc-parallel` |
| 并行+汇总 | — | `fanout` | `/cc-fanout` |
| 实现后验证 | verification-before-completion | `verify` | `/cc-verify` |
| 条件执行 | — | `branch` | `/cc-branch` |
| 方案竞争 | brainstorming（提出方案阶段） | `tournament` | `/cc-tournament` |
| 循环直到达标 | — | `loop_until` | `/cc-loop-until` |
| 任务分类路由 | — | `classify` | `/cc-classify` |
| 代码审查 | requesting-code-review | `pipeline` | `/cc-pipeline` |

### 常见陷阱

| 陷阱 | 正确做法 |
|------|---------|
| 在 cc-workflows 里用 `--interactive` | ❌ Claude Code 子进程无 TTY，会 EOFError。需求澄清在对话内完成 |
| 信任 agent 的 "success" 报告 | ❌ 用 superpowers verification-before-completion：跑测试、看输出、再下结论 |
| 一个大 prompt 塞进 loop | ❌ 每段 prompt 控制在 2000 字以内，拆成更多段 |
| 主会话跑长任务直到上下文溢出 | ❌ 超过 20 步就切到 cc-workflows loop，靠 resume 管理上下文 |
| parallel 任务之间有依赖 | ❌ 只对独立任务用 parallel，有依赖的用 pipeline |
| 跳过 review | ❌ superpowers 要求 spec review + code quality review，不可省略 |

### 输出解析

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

## 故障排查

| 现象 | 解决方法 |
|------|---------|
| `claude: command not found` | 在脚本中设置 `claude` 的完整路径（常见路径：`/Users/<用户>/.local/bin/claude`） |
| `--interactive` 报 `EOFError` | `--interactive` 需要 TTY。去掉该参数，在 Claude Code 对话中先完成需求澄清 |
| `result.result` 为空 | 正常现象 — 解析器会自动回退到 `assistant` 事件的 text 块 |
| Worktree 合并冲突 | Worktree 保留在 `/tmp/orchestrator-worktrees/orchestrator-<name>`，手动解决后在项目根执行 `git merge --no-edit orchestrator-<name>` |
| 状态文件过大 | 执行 `python3 cc_workflows.py loop "dummy" --max-steps 0` 可重置状态（完成 pending loop 并清空） |

## 开源协议

[MIT](LICENSE) — feel free to use, modify, and distribute.
