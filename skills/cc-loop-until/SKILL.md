---
name: cc-loop-until
description: >-
  重复执行直到满足停止条件。触发词：loop until、直到满足、持续循环、条件停止。
version: 1.0.0
---

# CC Loop Until

Loop until done 模式：重复执行任务，直到满足停止条件。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py loop_until \
  "修复所有 failing tests" \
  --stop-condition "所有测试通过" \
  --max-iterations 10
```

## 流程

1. 执行任务
2. 检查停止条件是否满足
3. 满足 → 输出结果
4. 不满足 → 继续执行
5. 达到 max-iterations → 输出最后结果并警告


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py loop_until "<任务>" --stop-condition "<条件>" [--agent <agent>] [--max-iterations <N>]
```
