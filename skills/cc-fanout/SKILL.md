---
name: cc-fanout
description: >-
  并发子任务执行后自动汇总。触发词：fanout、并发、分发、汇总。
version: 1.0.0
---

# CC Fanout

Fan-out-and-synthesize 模式：将大任务拆成多个子任务并发执行，最后自动汇总结果。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py fanout \
  "分析整个 src/ 目录的代码质量" \
  --subtask "分析 src/auth.py" --agent Explore \
  --subtask "分析 src/api.py" --agent Explore \
  --subtask "分析 src/utils.py" --agent Explore
```

## 说明

- 子任务并发执行，各自有独立 session
- 所有子任务完成后自动汇总结果
- 错误隔离：单个子任务失败不影响其他


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py fanout "<总任务>" --subtask "<子任务1>" --agent <agent> [--subtask "<子任务2>" ...]
```
