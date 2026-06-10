---
name: cc-tournament
description: >-
  N 个 agent 竞争同一任务，judge 评比选出胜者。触发词：tournament、竞赛、比赛、择优。
version: 1.0.0
---

# CC Tournament

Tournament 模式：N 个 agent 独立完成同一任务，judge agent 评比选出最优结果。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py tournament \
  "实现一个 LRU cache" \
  --contestants 3 \
  --agent general-purpose \
  --judge-agent Explore
```

## 流程

1. N 个 contestant 并发执行同一任务
2. judge agent 评估所有结果
3. 输出 winner 及评分理由


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py tournament "<任务>" --contestants <N> [--agent <agent>] [--judge-agent <agent>]
```
