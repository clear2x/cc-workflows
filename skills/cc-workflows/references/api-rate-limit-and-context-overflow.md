# API 限流与上下文溢出应对

## 现象

`claude -p` 调用挂住直到 300s 超时，不返回任何错误。原因：自定义 API endpoint 返回 `rate_limit_error`，但 claude CLI 不把这个当成可处理错误，而是静默等待直到 timeout。

## 确认方法

```bash
# 1. 确认 claude 可用
claude --version

# 2. 最小请求测试（不走 -p，走 agents 子命令更快）
CC_CLAUDE_CMD=~/.local/bin/claude \
  python3 cc_workflows.py agents

# 3. 直接 curl 测试 endpoint（ bypass claude CLI）
curl -s --max-time 10 "$ANTHROPIC_BASE_URL/v1/messages" \
  -H "x-api-key: $ANTHROPIC_AUTH_TOKEN" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"glm-5.1","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
```

如果 curl 返回 `rate_limit_error`，所有 `claude -p` 调用都会 hang，不是脚本问题。

## 长任务上下文管理

- 每段 `--max-turns 6~8`，多分段 (`--max-steps 50~100`)
- 靠 `--resume` 的 session 机制清空上下文，不要靠单段塞大量内容
- Python subprocess 调用时设 `PYTHONUNBUFFERED=1`，否则看不到实时输出
- 后台跑：`background=true` + `notify_on_complete=true`

## 相关 skill

`cc-workflows` SKILL.md 里也有长任务策略章节。
