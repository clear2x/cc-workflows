---
name: cc-workflows
description: >
  多 Agent 动态工作流调度器。基于 claude -p 实现 12 种模式：6 个 CLI 原语
  （agents/run/pipeline/branch/parallel/loop）+ 6 个官方 Workflow Pattern
  （classify/fanout/verify/genfilter/tournament/loop_until）。
  当用户提到"长时间跑"、"多 agent"、"工作流"、"pipeline"、"parallel"、"并行"、
  "条件分支"、"orchestrator"、"调度"、"分类"、"扇出"、"验证"、"筛选"、
  "锦标赛"、"循环直到"、"竞赛"时触发。不用于交互模式。
version: 2.0.0
---

# Claude Orchestrator Skill

本 skill 提供 **12 种模式** 的动态工作流调度，全部基于 `claude -p` 实现。

脚本路径（Hermes 全局）：`/Users/clear2x/.hermes/skills/cc-workflows/cc_workflows.py`
脚本路径（Claude Code 用户级）：`~/.claude/skills/cc-workflows/cc_workflows.py`
脚本路径（项目级）：`.claude/scripts/cc_workflows.py`
支持文件：`references/output-parsing.md`（JSON 输出解析参考）、`references/api-rate-limit-and-context-overflow.md`（API 限流与上下文溢出应对）、`references/test-project-verify.md`（test_project 全模式验证记录）、`references/test-results-12-modes.md`（12 种模式实测结果与已知问题）、`references/installation.md`（Claude Code 安装状态与修复步骤）、`references/gen-video-standalone.md`（gen-video 独立编排器的设计决策与调用方式）

## 输出解析注意

Claude Code 的 `--output-format json` 输出中，`result.result` 字段经常为空字符串。实际文本内容在 preceding `assistant` 事件的 `message.content[].text` 块中。详见 `references/output-parsing.md`。

## 触发条件

- 用户说"长时间跑"、"多 agent"、"工作流"、"pipeline"、"parallel"、"并行"
- 用户提到"条件分支"、"orchestrator"、"调度"、"loop --max-steps"
- 用户说"帮我跑一个长任务"、"分段执行"、"100 段"
- 用户说"分类"、"扇出"、"验证"、"筛选"、"锦标赛"、"循环直到"、"竞赛"
- 任务预计超过 12 轮工具调用，或需要多个 agent 协作

## 12 种模式

### 模式 1: 查看可用 agent

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py agents
```

从 system init 事件读取，不依赖模型输出，30 秒超时。

### 模式 2: 单 agent 执行

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py run "任务描述" --agent Explore
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py run "任务描述" --agent Plan --model step-3.7-flash
```

支持 agent：`Explore`, `Plan`, `general-purpose`, `claude`, `search-agent` 等。
自动续接上次会话。

### 模式 3: 多 agent 流水线（顺序执行）

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py pipeline \
  --step "探索:列出所有 .py 文件" --agent Explore \
  --step "分析:评估复杂度" --agent general-purpose \
  --step "规划:给出重构方案" --agent Plan
```

每个 step 可以指定不同 agent，自动续接上一步的 session。

### 模式 4: 条件分支

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py pipeline \
  --step "扫描:找出所有安全问题" --agent Explore \
  --step "判断:统计高危问题数" --agent general-purpose \
  --step "修复:生成修复方案（满足条件时执行）" --agent general-purpose \
  --step "跳过:记录无问题（不满足时执行）" --agent general-purpose \
  --if "高危问题数 > 0" --then-step 3 --else-step 4
```

条件语法：
- 数值比较：`高危问题数 > 0`, `count >= 5`, `severity == 3`
- 字符串包含：`output contains 'error'`, `result contains 'PASS'`

### 模式 5: 并行派发

```bash
python3 /Users/clear2x/hermes_ws/cc_workflows.py parallel \
  --task "分析 src/a.py" --agent Explore --name task_a \
  --task "分析 src/b.py" --agent Explore --name task_b \
  --task "分析 src/c.py" --agent general-purpose --name task_c
```

每个任务独立执行，各自有独立 session_id，错误隔离，互不影响。
最多 8 个并发 worker，超时 310 秒。

**默认开启 worktree 隔离**：每个任务自动在 `/tmp/orchestrator-worktrees/orchestrator-<name>` 创建独立 git worktree。执行完后**默认自动合并**回当前分支并清理 worktree，改动直接回到主分支。
**跳过合并保留 worktree**：加 `--keep-worktree`，执行完后跳过合并和清理，worktree 保留在 `/tmp/orchestrator-worktrees/orchestrator-<name>`，适合需要 inspect 或手动合并的场景。
**关闭隔离**：加 `--no-worktree`，所有任务直接在当前目录执行，无 worktree 隔离。

Worktree 实现细节：
1. 执行完后**默认自动 `git merge --no-edit` 合并到当前分支**
2. 合并成功 → 清理 worktree
3. 合并失败（有冲突）→ 保留 worktree，打印手动解决命令
4. `--keep-worktree` → 跳过合并和清理，worktree 保留
5. 创建前自动清理残留 worktree 和分支（处理异常中断的情况）
6. 执行失败时自动回退到共享目录
7. finally 块保证正确处理（合并 或 清理 或 保留）
8. 分支名格式：`orchestrator-<name>`

### 模式 6: 长任务自动循环

**核心行为**：prompt 按换行拆成独立步骤，每段执行一步，自动续接到下一步，直到全部完成或达到 `--max-steps` 上限。支持断点续接。

```bash
# 每行一步，自动分段执行
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop "Step 1: list files
Step 2: read calculator.py
Step 3: read logger.py
Step 4: report findings"

# 指定最多 50 段
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop "Step 1: ..." --max-steps 50

# 指定 agent
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop "Step 1: ..." --max-steps 100 --agent Explore
```

自动循环行为：
1. 将 prompt 按换行拆成独立步骤列表
2. 每段执行一步（带最近 3 步的上下文摘要）
3. 如果未完成（`stop_reason != end_turn` 或还有剩余步骤），自动续接下一步
4. 重复直到全部完成或达到 `--max-steps` 上限
5. 每段之间自动保存 `session_id` 和 `remaining_steps` 到 `/tmp/claude_orchestrator_state.json`
6. 中断后重新运行，自动从上次停止的步骤继续（断点续接）
7. 全部完成后输出累计统计（步数、轮数、费用），并清理状态
8. 如果上次已完成（`end_turn` 且无剩余步骤），重新开始而非继续

**断点续接示例**：
```bash
# 第一次跑 2 步
python3 cc_workflows.py loop "Step 1: list files
Step 2: read a.py
Step 3: read b.py
Step 4: report" --max-steps 2
# 输出：还剩 2 步未执行

# 第二次继续（无需改 prompt）
python3 cc_workflows.py loop "Step 1: list files
Step 2: read a.py
Step 3: read b.py
Step 4: report" --max-steps 2
# 输出：从上次中断处继续，还剩 2 步... Step 3 → Step 4
```

### 查看会话状态

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py sessions
```

---

## 6 种官方 Workflow Pattern

### 模式 7: classify — 分类路由（Classify-and-act）

先用 classifier agent 分类任务，再路由到对应 action。

```bash
python3 ~/.claude/skills/cc-workflows/cc_workflows.py classify "这段代码有安全漏洞" \
  --class-security "执行安全审计" \
  --class-performance "执行性能分析" \
  --default "一般分析"
```

### 模式 8: fanout — 扇出聚合（Fan-out-and-synthesize）

并发执行子任务，然后汇总结果。

```bash
python3 ~/.claude/skills/cc-workflows/cc_workflows.py fanout "分析代码" \
  --subtask "检查 auth.py" --name auth \
  --subtask "检查 api.py" --name api \
  --synthesize "汇总成报告"
```

### 模式 9: verify — 对抗验证（Adversarial verification）

执行任务后用 verifier 对抗式验证，可迭代修复。

```bash
python3 ~/.claude/skills/cc-workflows/cc_workflows.py verify "实现功能 X" \
  --rubric "必须有测试、错误处理、符合风格指南" \
  --max-rounds 2
```

### 模式 10: genfilter — 生成过滤（Generate-and-filter）

生成 N 个方案，用 rubric 筛选出最好的 K 个。

```bash
python3 ~/.claude/skills/cc-workflows/cc_workflows.py genfilter "给产品起名" \
  --count 3 --rubric "简短好记" --filter-top 1
```

### 模式 11: tournament — 锦标赛（Tournament）

N 个 agent 竞争同一任务，judge 评比选出赢家。

```bash
python3 ~/.claude/skills/cc-workflows/cc_workflows.py tournament "实现 LRU 缓存" \
  --contestants 3 --judge "最优：正确、快速、可读"
```

### 模式 12: loop_until — 条件循环（Loop until done）

循环执行任务，每轮检查停止条件，满足则退出。

```bash
python3 ~/.claude/skills/cc-workflows/cc_workflows.py loop_until "修复所有失败的测试" \
  --stop-condition "所有 pytest 测试通过" \
  --max-iterations 10
```

---

## 关键规则

1. **每段最多 12 轮**：不要改 `MAX_TURNS`，除非用户明确要求
2. **必须使用脚本**：不要直接调用 `claude` 命令（脚本封装了参数和解析）
3. **交互模式只用于 loop**：`--interactive` 仅在 loop 模式可用，用于启动前 Superpowers brainstorming 式需求澄清
4. **不要手动 compact**：靠 `--resume` 实现上下文清空
5. **并行任务独立**：每个任务有独立 session_id，一个失败不影响其他
6. **条件分支**：step 之间共享 context（last_output, last_turns），条件基于这些变量评估
7. **每段结束后汇报**：告诉用户"Step N 完成，费用 $X"
8. **agents 命令快速**：30 秒超时，从 init 事件读取，不调用模型
9. **result.result 可能为空**：见 `references/output-parsing.md`
10. **pipeline step 计数**：脚本里 step 序号从 1 开始，`--step` 定义数和实际执行数要对应，避免 off-by-one
11. **loop 重开逻辑**：如果上次循环以 `end_turn` 结束（任务完成），再次调用 `loop` 会全新开始，不会续接旧会话

## 在 Claude Code 中使用

Claude Code 会自动加载 `~/.claude/skills/` 下的技能（通过 `SKILL.md` 发现）。

### 自动触发方式

在项目目录下启动 `claude`，直接对 Claude 说需求，例如：

> 用 cc-workflows loop 重构 src/，最多 50 步

> 并行分析这三个文件：a.py, b.py, c.py

Claude 会读取 skill 文档，**直接通过 terminal 工具执行命令**，不只是构造命令。长任务用 `background=true` + `notify_on_complete=true` 后台运行，跑完后 Claude 会汇报结果。

### 触发关键词

- "长时间跑"、"分段执行"、"100 段"、"loop"
- "多 agent"、"并行"、"parallel"
- "流水线"、"pipeline"、"条件分支"
- "orchestrator"、"调度"

### ⚠️ 重要限制：`--interactive` 不适用于 Claude Code

`--interactive` 需要真实 TTY，Claude Code 的子进程通常没有，会导致 `EOFError`。**不要在 Claude Code 里用 `--interactive`**。需求澄清应该在 Claude Code 对话里完成，确认后再执行脚本。

### 安装要求

Claude Code 用户级路径必须包含 `SKILL.md`：

```
~/.claude/skills/cc-workflows/
├── SKILL.md          ← 必须存在，否则 Claude Code 不会加载此 skill
└── cc_workflows.py
```

如果 `~/.claude/skills/cc-workflows/` 下没有 `SKILL.md`，需要手动复制 Hermes 全局版本的 `SKILL.md` 过去。

## 安装位置

| 作用域 | 路径 | 说明 |
|--------|------|------|
| Hermes 全局 | `/Users/clear2x/.hermes/skills/cc-workflows/cc_workflows.py` | Hermes Agent 使用 |
| Claude Code 用户级 | `~/.claude/skills/cc-workflows/cc_workflows.py` + `SKILL.md` | Claude Code 自动加载 |
| 项目级 | `.claude/skills/cc-workflows/SKILL.md`（文档）+ 脚本软链接 | 项目共享 |

Claude Code 会自动加载 `~/.claude/skills/` 下包含 `SKILL.md` 的技能。

## 与 Superpowers 结合使用

Superpowers（obra/superpowers）是一套编码代理的开发方法论，包含 TDD、subagent-driven-development、writing-plans、brainstorming 等 skill。

### 安装 Superpowers（Claude Code）

```bash
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

已注册 marketplace 路径：`/Users/clear2x/.claude/plugins/marketplaces/superpowers-marketplace`

### 集成模式

**方案 A：orchestrator 注入 Superpowers 约束到 agent prompt**

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop \
  "重构 src/calculator.py，遵循 TDD：先写失败测试，再写代码，再重构" \
  --max-steps 100 \
  --agent general-purpose
```

**方案 B：Claude Code 主会话自动触发**

在项目目录下启动 `claude`，对 Claude 说：

> 用 Superpowers 的 subagent-driven-development 重构 src/，每步跑测试，最多 100 段

Claude 会自动加载 Superpowers 的 `writing-plans`、`subagent-driven-development`、`test-driven-development` 等 skill，同时 `cc-workflows` 会被触发用于长任务循环。

### 推荐组合

| Superpowers skill | cc-workflows 模式 | 用途 |
|-------------------|--------------------------|------|
| `brainstorming` | `run` | 设计阶段探索方案 |
| `writing-plans` | `pipeline` | 将设计拆成实施计划 |
| `subagent-driven-development` | `parallel` | 多任务并行实施 |
| `test-driven-development` | `loop` | 长任务 TDD 循环 |
| `requesting-code-review` | `pipeline` | 条件分支触发代码审查 |

## 集成 Superpowers

`cc-workflows` 已内置 Superpowers 工作流约束自动注入。loop 模式下，每段会根据关键词自动注入对应 skill 的规范（TDD、writing-plans、subagent-driven-development 等）。

详见：`references/superpowers-integration.md`

## 注意事项

- 脚本路径：`~/.hermes/skills/cc-workflows/cc_workflows.py`
- 状态文件：`/tmp/claude_orchestrator_state.json`，重启不丢失
- 工作目录：自动检测 git root，失败则回退到当前执行目录。**不再硬编码单一项目路径**
- 如果 `run` 或 `resume` 报错，先查看错误信息，再决定是否重试
- 并行模式下最多 8 个并发 worker，超时 310 秒（CLAUDE_TIMEOUT + 10）
- **`--keep-worktree`**：parallel 模式下加此参数，worktree 执行完后**跳过合并和清理**，改动保留在 `/tmp/orchestrator-worktrees/orchestrator-<name>`。**不加此参数时，默认会自动合并并清理**
- **默认自动合并**：parallel 任务执行完后自动 `git merge --no-edit` 合并到当前分支。合并成功则清理 worktree；合并冲突则保留 worktree 并打印手动解决命令
- `--dangerously-skip-permissions` 已内置，无需额外传递

## 脚本路径配置

脚本通过以下顺序解析 `claude` 实际路径：

1. 环境变量 `CC_CLAUDE_CMD`（优先级最高）
2. 默认 fallback：`~/.local/bin/claude`

如果 `claude` 不在 PATH 中，运行时显式指定：

```bash
CC_CLAUDE_CMD=/Users/clear2x/.local/bin/claude \
  python3 ~/.hermes/skills/cc-workflows/cc_workflows.py agents
```

`agents` 和 `sessions` 子命令走的是 `claude agents --json`（不走 `-p`），即使 API 暂时不可用也可能正常工作，可用它们快速验证脚本连通性。

## 长任务与上下文管理

长任务（超过 20 段）推荐策略：

- **低轮次 + 多分段**：每段 `--max-turns 6~8`，靠 `--max-steps` 增加总段数。上下文清空靠 `--resume` 的 session 机制，不要靠单段塞大量内容。
- **后台运行**：在 Claude Code 里用 `background=true` + `notify_on_complete=true` 跑 loop，长任务不占前台。
- **Python 调用时设 unbuffered**：如果从 Python subprocess 调用 cc_workflows.py，设 `PYTHONUNBUFFERED=1` 或 `python3 -u`，否则实时输出被缓冲，看不到进度。
- **避免单段 prompt 过长**：loop 每段 prompt 控制在 2000 字以内；如果任务描述本身很长，拆成更多段而不是塞进一段。

## Unicode 与输出解析陷阱

- **subprocess 不要用 `text=True`**：长输出可能触发 `UnicodeDecodeError: 'utf-8' codec can't decode bytes`。改用 `capture_output=True` + 手动 `decode('utf-8', errors='replace')`。
- **`_parse_claude_output` 要传入 str**：确保传入的是解码后的 str，不要传 bytes。
- **classify 分类匹配不够健壮**：classifier 经常返回解释性长文本（"你目前没有描述具体的 bug 详情..."），而不是关键词。当前 `key.lower() in classification` 会误匹配。建议：在 classify prompt 里明确要求 "Reply with exactly one word: <key1>, <key2>, or <key3>"，或者改匹配逻辑为取输出前几个 token 匹配。
- **`result.result` 为空是正常的**：parser 会自动回退到 `assistant` 事件的 text 块，不要因为 `result.result == ""` 就认为执行失败。

## API 限流与超时处理

如果 `claude -p` 调用持续超时（300s）且不返回错误，可能是 API 限流（尤其自定义 endpoint 的 `rate_limit_error`）。此时：

1. 用 `claude --version` 和 `claude -p "echo ok" --max-turns 1 --dangerously-skip-permissions` 快速确认是网络问题还是脚本问题
2. 如果 API 返回 `rate_limit_error`，所有后续 `claude -p` 调用都会 hang 到超时，不是脚本 bug
3. 等限额恢复后重试；长任务建议分段跑，每段独立，避免一次性挂住太久

## 已知修复记录

- **输出解析器修复**：`result.result` 为空时，回退从 `assistant` 事件的 `text` 块提取内容
- **model 字段修复**：`result.model` 为空时，回退从 `result.modelUsage` 取第一个 key
- **agents 命令修复**：改为从 system init 事件读取 agent 列表，不依赖模型输出；忽略 returncode
- **并行稳定性修复**：增加 task 级 try/except 和 future.result(timeout)
- **pipeline 修复**：第一段执行后手动设置 `step_idx = 1`，避免重复执行
- **loop 分段修复**：将 prompt 按换行拆成独立步骤，每段执行一步，支持断点续接；中断后重新运行自动从上次停止处继续
- **loop 完成状态修复**：上次以 `end_turn` 完成且无剩余步骤时，重新开始而非错误续接
- **branch 条件变量提取修复**：`evaluate_condition` 现在会从 `last_output` 里用正则 `key = <number>` 提取数值变量，不再只查 context 字典
- **branch next_step 修复**：初始状态 `next_step` 改为 1（而非 2），避免跳过第一个 step
- **branch 条件判断点修复**：条件评估改在 designated condition step 执行，而非每步都检查
- **worktree 冲突修复**：创建 worktree 前自动清理残留分支和目录，防止 `fatal: a branch named ... already exists`
- **run_claude cwd 支持**：新增 `cwd` 参数，允许 parallel 任务在独立 worktree 中执行
- **parallel 默认 worktree**：默认开启 worktree 隔离，`--no-worktree` 关闭；支持残留清理和 finally 清理
- **PROJECT_DIR 自动检测**：通过 `git rev-parse --show-toplevel` 自动检测 git root，失败回退 `Path.cwd()`。切换项目无需手动改脚本
- **worktree 默认自动合并**：parallel 任务执行完后默认自动 `git merge --no-edit` 合并到当前分支。合并成功清理 worktree；合并冲突则保留 worktree 并打印手动解决命令
- **`--keep-worktree` 参数**：parallel 模式下新增 `--keep-worktree`，执行完后跳过合并和清理，worktree 保留在 `/tmp/orchestrator-worktrees/orchestrator-<name>`
