---
name: cc-genfilter
description: >-
  生成 N 个方案后用 rubric 筛选 Top K。触发词：genfilter、生成筛选、多方案比较。
version: 1.0.0
---

# CC Genfilter

Generate-and-filter 模式：生成 N 个独立方案，然后用 rubric 筛选出最好的 K 个。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py genfilter \
  "为这个 CLI 工具想 5 个名字" \
  --count 5 --filter-top 3 \
  --rubric "好记、简短、与工具功能相关"
```

## 流程

1. 生成阶段：并发生成 N 个独立方案
2. 筛选阶段：用 rubric 评估所有方案，排序
3. 输出 Top K 方案详情


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py genfilter "<生成任务>" --count <N> --filter-top <K> [--rubric "<筛选标准>"]
```
