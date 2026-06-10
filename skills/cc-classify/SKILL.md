---
name: cc-classify
description: >-
  分类任务并路由到不同 agent/步骤。触发词：classify、分类、判断类型、路由。
version: 1.0.0
---

# CC Classify

Classify-and-act 模式：先用 agent 对任务分类，再路由到对应处理步骤。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py classify \
  "这个 bug 是 security 还是 performance 问题？" \
  --agent Explore \
  --route-security "修复安全问题" --agent general-purpose \
  --route-performance "优化性能" --agent general-purpose \
  --default "记录待处理" --agent Plan
```

## 说明

- classifier agent 输出分类结果
- 匹配 `--route-<类名>` 执行对应步骤
- `--default` 处理未匹配的情况


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py classify "<分类任务>" --agent <agent> [--route-<类名> "<步骤>" ...]
```
