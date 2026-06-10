# Claude Workflow Orchestrator

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
- [安装](#安装)
- [6 个 CLI 原语](#6-个-cli-原语)
  - [模式 1 — `agents`](#模式-1--agents)
  - [模式 2 — `run`](#模式-2--run)
  - [模式 3 — `pipeline`](#模式-3--pipeline)
  - [模式 4 — `branch`](#模式-4--branch)
  - [模式 5 — `parallel`](#模式-5--parallel)
  - [模式 6 — `loop`](#模式-6--loop)
  - [`sessions`](#sessions)
- [6 种官方 Workflow 模式](#6-种官方-workflow-模式)
  - [模式 1 — `classify`](#模式-1--classify)
  - [模式 2 — `fanout`](#模式-2--fanout)
  - [模式 3 — `verify`](#模式-3--verify)
  - [模式 4 — `genfilter`](#模式-4--genfilter)
  - [模式 5 — `tournament`](#模式-5--tournament)
  - [模式 6 — `loop_until`](#模式-6--loop_until)
- [CLI 参考](#cli-参考)
- [高级功能](#高级功能)
- [Superpowers 集成](#superpowers-集成)
- [输出解析](#输出解析)
- [故障排查](#故障排查)
- [开源协议](#开源协议)

---

<a name="概述"></a>
## 概述

Claude Orchestrator 是一个**生产级**的 Python 封装，底层调用 `claude -p`（Claude Code 的非交互无头模式）。它将一次性 prompt 转化为**可重复执行、断点续接、可观测**的工作流，全程在终端完成。

### 12 种执行模式一览

| 模式 | 说明 |
|------|------|
| `run` | 单 agent 执行，自动续接 |
| `pipeline` | 顺序多 agent 流水线 |
| `branch` | 条件分支流水线 |
| `parallel` | 并行派发，带 git worktree 隔离 |
| `loop` | 长任务分段循环，支持断点续接 |
| `sessions` | 查看活跃 Claude 会话 |

### 快速开始

```bash
# 1. 安装（一条命令）
npx skills add https://github.com/clear2x/claude-workflow-orchestrator

# 2. 验证可用 agent
python3 ~/.hermes/skills/claude-workflow-orchestrator/claude_orchestrator.py agents

# 3. 单任务执行
python3 ~/.hermes/skills/claude-workflow-orchestrator/claude_orchestrator.py run \
  "重构 auth.py，添加类型提示" \
  --agent general-purpose

# 4. 长任务分段执行（自动断点续接）
python3 ~/.hermes/skills/claude-workflow-orchestrator/claude_orchestrator.py loop \
  "第 1 步: 列出 src/ 下所有 .py 文件
第 2 步: 读取 auth.py 并总结结构
第 3 步: 读取 api.py 并总结结构
第 4 步: 写一份涵盖两个文件的重构方案" \
  --max-steps 100
```

### 与官方 Dynamic Workflows 的差异

Claude Code 的官方 [dynamic workflows](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) 允许 Claude **现场编写并编排自己的 JavaScript harness**。该体系暴露了 6 个 workflow **设计模式**（Classify-and-act、Fan-out-and-synthesize、Adversarial verification、Generate-and-filter、Tournament、Loop until done），Claude 将它们作为 JS 代码组合在 workflow 文件里。

Claude Orchestrator 走的是另一条路线：它提供 6 个 CLI **执行原语** 和 6 个原生实现的 **官方 workflow pattern** — 固定的、带有 opinionated 的命令模式，底层封装 `claude -p`，并替你处理工作树、状态持久化、断点续接、Superpowers 注入等编排细节，无需手写任何 JS。

| 官方设计模式 | Orchestrator 对应命令 | 说明 |
|--------------|----------------------|------|
| Classify-and-act | `classify` | 分类后路由到不同 agent |
| Fan-out-and-synthesize | `fanout` | 并发子任务 + 自动汇总 |
| Adversarial verification | `verify` | 执行后对抗式验证 + 自动修复 |
| Generate-and-filter | `genfilter` | 生成 N 方案，rubric 筛选 Top K |
| Tournament | `tournament` | N 个 agent 竞争，judge 评比 |
| Loop until done | `loop_until` | 满足停止条件前持续循环 |

| 官方原语 |  Orchestrator 模式 | 说明 |
|----------|-------------------|------|
| 单 agent | `run` | 单次执行，支持自动续接 |
| 流水线 | `pipeline` | 顺序多 agent 流水线 |
| 条件分支 | `branch` | 根据条件选择不同步骤 |
| 并行派发 | `parallel` | 并发执行，带 git worktree 隔离 |
| 长任务循环 | `loop` | 分段循环，支持断点续接 |
| 会话查看 | `sessions` | 查看活跃 Claude 会话 |

总结：官方 dynamic workflows 是 **Claude 自己写 JS、更灵活**；Claude Orchestrator 是 **用户通过 CLI 调用、更可预期、可复用、可分享**。如果你想要不写 JS 就能获得稳定、可复用的编排命令，用 Orchestrator。

## 安装

### 方式 A：`npx skills add`（推荐，一条命令）

```bash
npx skills add https://github.com/clear2x/claude-workflow-orchestrator
```

会自动将 `skills/claude-workflow-orchestrator/` 文件夹复制到本地技能目录。

安装单个 skill（按 install name）：

```bash
npx skills add https://github.com/clear2x/claude-workflow-orchestrator --skill "claude-workflow-orchestrator"
```

### 方式 B：`install.py`

```bash
git clone https://github.com/clear2x/claude-workflow-orchestrator.git
cd claude-workflow-orchestrator
python3 install.py
```

安装位置：
- `~/.hermes/skills/claude-workflow-orchestrator/claude_orchestrator.py` — Hermes Agent 用
- `~/.claude/skills/claude-workflow-orchestrator/claude_orchestrator.py` + `SKILL.md` — Claude Code 用

### 方式 C：手动复制

```bash
# Claude Code 项目级
mkdir -p .claude/skills/claude-workflow-orchestrator
cp skills/claude-workflow-orchestrator/claude_orchestrator.py .claude/skills/claude-workflow-orchestrator/
cp skills/claude-workflow-orchestrator/SKILL.md .claude/skills/claude-workflow-orchestrator/
```

```bash
# Hermes Agent 全局
mkdir -p ~/.hermes/skills/claude-workflow-orchestrator
cp skills/claude-workflow-orchestrator/claude_orchestrator.py ~/.hermes/skills/claude-workflow-orchestrator/
```

## 12 种执行模式

### 原语 1 — `agents`：查看可用 agent

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

### 原语 2 — `run`：单 agent 执行

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

### 原语 3 — `pipeline`：多 agent 流水线（顺序执行）

每一步可使用不同 agent，session 自动续接。

```bash
python3 claude_orchestrator.py pipeline \
  --step "Explore: 列出 src/ 下所有 .py 文件" --agent Explore \
  --step "Analyze: 评估每个文件的圈复杂度" --agent general-purpose \
  --step "Plan: 给出重构方案" --agent Plan
```

### 原语 4 — `branch`：条件分支

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

### 原语 5 — `parallel`：并行派发

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

### 原语 6 — `loop`：长任务自动循环

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

### `sessions`：查看会话状态

```bash
python3 claude_orchestrator.py sessions
```

## 6 种官方 Workflow 模式

Claude Code 的官方 [dynamic workflows](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) 暴露了 6 个 workflow **设计模式**（Classify-and-act、Fan-out-and-synthesize、Adversarial verification、Generate-and-filter、Tournament、Loop until done）。这些模式原本需要 Claude 现场编写 JavaScript 来组合；Claude Orchestrator 将它们直接实现为原生 CLI 命令，无需编写任何 JS 工作流文件。

### 原语 1 — `classify`（Classify-and-act）

先用一个 classifier agent 对任务进行分类，再根据分类结果路由到不同的 agent/行为。

```bash
python3 claude_orchestrator.py classify \
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

### 原语 2 — `fanout`（Fan-out-and-synthesize）

将任务拆分为多个小步骤，每个步骤由独立的 agent 并发执行，最后汇总所有结果。

```bash
python3 claude_orchestrator.py fanout \
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

### 原语 3 — `verify`（Adversarial verification）

执行任务，然后由独立的 verifier agent 根据 rubric 对抗式地检查输出质量，不合格则自动修复，循环至通过或达到最大轮数。

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

执行流程：
1. 主 agent 执行任务
2. verifier agent（默认 `Explore`）根据 rubric 评分
3. 如果 FAIL，主 agent 获得问题列表并生成修正版本
4. 循环最多 `--max-rounds` 次
5. 输出最终（ hopefully verified）结果

### 原语 4 — `genfilter`（Generate-and-filter）

生成 N 个方案，再用 rubric 进行评分筛选，只返回质量最高的 K 个候选。

```bash
python3 claude_orchestrator.py genfilter \
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

### 原语 5 — `tournament`（Tournament）

N 个 agent 使用不同方法竞争同一个任务，由 judge agent  pairwise 评比选出最终赢家。

```bash
python3 claude_orchestrator.py tournament \
  "Implement a thread-safe LRU cache in Python" \
  --contestants 3 \
  --judge "Best solution: correct thread safety, O(1) get/put, clean code, good tests"
```

执行流程：
1. 启动 `--contestants` 个 agent，每个采用不同的 "approach" 风格（direct / robust / optimized / creative / standard）
2. 所有参赛者并发执行，使用独立 worktree 隔离
3. judge agent（`Explore`）根据任务要求和 judge prompt 对全部提交进行 pairwise 评估
4. 宣布获胜者，附上评分 breakdown

### 原语 6 — `loop_until`（Loop until done）

对工作量不确定的任务，循环执行直到满足停止条件（而非固定次数）。

```bash
python3 claude_orchestrator.py loop_until \
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
python3 claude_orchestrator.py <命令> [选项]

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

## Superpowers 集成

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

## 故障排查

| 现象 | 解决方法 |
|------|---------|
| `claude: command not found` | 在脚本中设置 `claude` 的完整路径（常见路径：`/Users/<用户>/.local/bin/claude`） |
| `--interactive` 报 `EOFError` | `--interactive` 需要 TTY。去掉该参数，在 Claude Code 对话中先完成需求澄清 |
| `result.result` 为空 | 正常现象 — 解析器会自动回退到 `assistant` 事件的 text 块 |
| Worktree 合并冲突 | Worktree 保留在 `/tmp/orchestrator-worktrees/orchestrator-<name>`，手动解决后在项目根执行 `git merge --no-edit orchestrator-<name>` |
| 状态文件过大 | 执行 `python3 claude_orchestrator.py loop "dummy" --max-steps 0` 可重置状态（完成 pending loop 并清空） |

## 开源协议

[MIT](LICENSE) — feel free to use, modify, and distribute.
