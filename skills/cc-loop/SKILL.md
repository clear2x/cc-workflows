---
name: cc-loop
description: >-
  长任务分段循环，按换行拆成独立步骤，支持断点续接。触发词：loop、循环、分段执行、长时间跑、100 段。
version: 1.0.0
---

# CC Loop

长任务自动分段循环。prompt 按换行拆成独立步骤，每步执行一步，自动续接。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop "Step 1: list files
Step 2: read calculator.py
Step 3: read logger.py
Step 4: report findings" --max-steps 100
```

## 断点续接

中断后重新运行同一命令，自动从上次停止处继续。

```bash
# 第一次：跑 2 步
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop "..." --max-steps 2

# 第二次：继续
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop "..." --max-steps 2
```

## 说明

- 每段最多 12 轮
- 状态保存在 `/tmp/claude_orchestrator_state.json`
- 如果上次已完成（end_turn），重新开始而非续接


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py loop "<多行prompt>" --max-steps <N> [--agent <agent>]
```
