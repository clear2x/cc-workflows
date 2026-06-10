# Claude Code JSON Output Parsing Reference

## Event Structure (`--output-format json`)

Claude Code streams events. The final `result` event often has an **empty `result` field** — the real assistant text lives in preceding `assistant` events' `message.content[].text` blocks.

### Canonical extraction order

1. Find the last `type: "result"` event.
2. Read `result.result` (may be `""`).
3. If empty, scan all `type: "assistant"` events and concatenate `message.content[i].text` where `content[i].type == "text"`.
4. `stop_reason` and `session_id` come from the `result` event.

### Model field

`result.model` is often `null`. Use `result.modelUsage` keys instead:

```python
model = last_result.get("model")
if not model:
    mu = last_result.get("modelUsage", {})
    if isinstance(mu, dict) and mu:
        model = list(mu.keys())[0]
```

### `agents` / `system init` event

When running `claude -p "echo ready" --max-turns 1`, the **first event** is always `type: system, subtype: init`. It contains:
- `agents`: list of available agent names
- `tools`: available tools
- `model`: active model

**Pitfall**: `returncode` may be non-zero even when stdout contains valid JSON with the init event. Do **not** gate parsing on `result.returncode == 0`. Parse stdout regardless.

### `stop_reason` values

| Value | Meaning |
|-------|---------|
| `end_turn` | Task completed normally |
| `max_turns` | Hit `--max-turns` limit, context still active |
| `tool_use` | Claude wants to call a tool (incomplete turn) |

When `stop_reason == "tool_use"` and `result.is_error == true` with `subtype: error_max_turns`, the session exhausted turns while waiting for tool results — treat as incomplete.
