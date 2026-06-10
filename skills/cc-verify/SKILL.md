---
name: cc-verify
description: >-
  执行任务后对抗式验证，不通过则自动修复重试。触发词：verify、验证、审查、确保通过。
version: 1.0.0
---

# CC Verify

Adversarial verification 模式：执行任务后，用 rubric 标准验证，不通过则自动修复重试。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py verify \
  "实现 LRU cache" \
  --rubric "必须有类型提示，必须有测试，必须通过 mypy" \
  --max-rounds 3
```

## 流程

1. 执行任务
2. 用 rubric 验证结果
3. 通过 → 输出结果
4. 不通过 → 自动修复，回到步骤 2
5. 达到 max-rounds 仍未通过 → 输出最后结果并警告


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py verify "<任务>" --rubric "<验证标准>" [--agent <agent>] [--max-rounds <N>]
```
