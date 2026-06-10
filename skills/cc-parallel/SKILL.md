---
name: cc-parallel
description: >-
  并行派发多个任务，默认 git worktree 隔离。触发词：parallel、并行、同时跑、多任务。
version: 1.0.0
---

# CC Parallel

并行派发多个独立任务，每个任务有独立 session_id，错误隔离。

## 用法

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py parallel \
  --task "分析 src/a.py" --agent Explore --name task_a \
  --task "分析 src/b.py" --agent Explore --name task_b \
  --task "分析 src/c.py" --agent general-purpose --name task_c
```

## Worktree 选项

- 默认：自动创建 worktree，执行完后自动合并回当前分支并清理
- `--keep-worktree`：保留 worktree，适合 inspect 或手动合并
- `--no-worktree`：关闭隔离，直接在当前目录执行

## 限制

- 最多 8 个并发 worker
- 超时 310 秒


## 快速命令

```bash
python3 ~/.hermes/skills/cc-workflows/claude_orchestrator.py parallel --task "<任务>" --agent <agent> --name <名> [--task ...] [--keep-worktree] [--no-worktree]
```
