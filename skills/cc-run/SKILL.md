---
name: cc-run
description: >-
  单 agent 执行任务，支持自动续接。触发词：run、执行、跑一下、单 agent。
version: 1.0.0
---

# CC Run

单 agent 执行任务，上次会话自动续接。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py run "<任务描述>" --agent general-purpose
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py run "<任务描述>" --agent Explore --model step-3.7-flash
```

## 常用 agent

- `Explore` — 探索代码库
- `Plan` — 规划方案
- `general-purpose` — 通用执行
- `claude` — Claude 主 agent


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py run "<任务>" --agent <agent名>
```
