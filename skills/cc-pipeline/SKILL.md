---
name: cc-pipeline
description: >-
  多 agent 顺序流水线，每步指定不同 agent。触发词：pipeline、流水线、顺序执行、多步。
version: 1.0.0
---

# CC Pipeline

多 agent 顺序流水线，每步可指定不同 agent，自动续接上一步 session。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py pipeline \
  --step "探索: 列出所有 .py 文件" --agent Explore \
  --step "分析: 评估复杂度" --agent general-purpose \
  --step "规划: 给出重构方案" --agent Plan
```

## 说明

- 每步自动携带上一步的输出作为上下文
- step 序号从 1 开始，注意对应关系


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py pipeline --step "<步骤>" --agent <agent> [--step "<步骤>" --agent <agent> ...]
```
