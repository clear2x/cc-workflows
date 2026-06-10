---
name: cc-agents
description: >-
  查看 Claude Code 可用 agent 列表。触发词：agents、查看 agent、列出 agent。
version: 1.0.0
---

# CC Agents

快速查看当前 Claude Code 可用的 agent 列表，无需调用模型。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py agents
```

## 说明

- 从 system init 事件读取 agent 列表，30 秒超时
- 不依赖模型输出，速度快


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py agents
```
