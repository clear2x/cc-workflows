# 12 种模式实测记录

实测环境：`CC_CLAUDE_CMD=/Users/clear2x/.local/bin/claude`，模型 `step-3.7-flash`（通过 ZhiPu GLM 5.1 endpoint）。

## 6 CLI 原语

| 模式 | 结果 | 备注 |
|------|------|------|
| `agents` | ✅ | 8 个 agent 正常列出 |
| `run` | ✅ | 单任务 1 turn，`$0.0492` |
| `pipeline` | ✅ | 3 步顺序执行，8 turns，`$0.2480` |
| `branch` | ✅ | 条件跳转正确，state 正常记录 |
| `parallel` | ⚠️ | worktree 创建失败（非 git repo），回退共享目录，功能正常 |
| `loop` | ✅ | 5 步分 3 次跑，断点续接完全正常 |

## 6 Official Workflow Patterns

| 模式 | 结果 | 备注 |
|------|------|------|
| `classify` | ⚠️ 部分 | classifier 返回解释性文本而非关键词，`key.lower() in classification` 误匹配。修复：prompt 里要求 "Reply with exactly one word: security, performance, or ui" |
| `fanout` | ✅ | 并发 + 汇总成功，`$0.1224` |
| `verify` | ✅ | 主任务 → FAIL → 修复 → PASS，2 轮完成 |
| `genfilter` | ✅ | 生成 9 条 slogan，Top 2 正确返回，中文 unicode 处理正常 |
| `tournament` | ✅ | 2 参赛者，judge 详细对比分析，选出获胜方案 |
| `loop_until` | ✅ | 条件 NOT_MET → MET，2 轮完成 |

## 已知脚本问题与修复

1. **硬编码 `"claude"`**：PATH 找不到时报 `FileNotFoundError`。修复：新增 `CLAUDE_CMD` 配置，默认 `~/.local/bin/claude`，支持 `CC_CLAUDE_CMD` 环境变量覆盖。
2. **`UnicodeDecodeError`**：`subprocess.run(text=True)` 长输出触发。修复：改用 `capture_output=True` + 手动 `decode('utf-8', errors='replace')`。
3. **`classify` 分类匹配**：classifier 返回解释性长文本导致误匹配。workaround：在 prompt 里明确要求输出单个关键词。
