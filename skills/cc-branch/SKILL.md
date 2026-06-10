---
name: cc-branch
description: >-
  条件分支流水线，根据上一步结果选择执行路径。触发词：branch、条件分支、if-then、判断后执行。
version: 1.0.0
---

# CC Branch

条件分支流水线。在执行到指定 step 后，根据条件选择下一个 step。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py pipeline \
  --step "扫描: 找出所有安全问题" --agent Explore \
  --step "判断: 统计高危问题数" --agent general-purpose \
  --step "修复: 生成修复方案（满足条件时执行）" --agent general-purpose \
  --step "跳过: 记录无问题（不满足时执行）" --agent general-purpose \
  --if "高危问题数 > 0" --then-step 3 --else-step 4
```

## 条件语法

- 数值比较：`count > 0`, `severity >= 3`
- 字符串包含：`output contains 'error'`


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/cc_workflows.py pipeline --step ... --if "<条件>" --then-step <N> --else-step <M>
```
