# Superpowers Integration Reference

## What Gets Injected

The orchestrator auto-detects keywords in each step prompt and injects the matching Superpowers skill constraint before the actual task text.

| Keyword pattern | Injected skill |
|---|---|
| tdd, test-driven, 测试驱动, 红绿重构 | test-driven-development |
| plan, 规划, 拆解, 任务分解 | writing-plans |
| subagent, 并行, 多 agent, 派发 | subagent-driven-development |
| review, 评审, code review | requesting-code-review |
| debug, 调试, 修复 bug, 排查 | systematic-debugging |
| anything else | generic workflow reminder |

## Verified Behavior

- TDD keyword triggers RED-GREEN-REFACTOR enforcement in a single-step loop test.
- Claude obeyed: wrote failing tests first, confirmed failure, then wrote minimal code, then refactored. 10/10 tests passed.
- Cost: ~$0.10–0.15 per step, 5–9 turns per step on small codebase.

## Interactive Mode (`--interactive`)

When `--interactive` is passed to `loop`, the orchestrator runs a Superpowers brainstorming-style pre-flight before executing any steps:

1. Generates 2–3 short clarifying questions via a single `claude -p` call
2. Prompts the user for answers (or `skip` to bypass)
3. Generates a refined prompt from the answers
4. Passes the refined prompt into the normal loop segmentation logic

Interactive mode is skipped when resuming from a saved state (`remaining_steps` already populated), so mid-run interruptions do not re-trigger clarification.

Fallbacks:
- If the question-generation call fails, the raw prompt is used as-is.
- If the refinement call fails or returns empty output, the raw prompt is used as-is.

## Pitfalls

- The keyword matcher is substring-based. `"subtract"` does NOT trigger TDD (good). But `"planning"` would trigger writing-plans (probably fine).
- Superpowers skills are loaded from the Claude Code plugin cache, not from this skill directory. The orchestrator only injects text prompts — it does not load skill files directly.
- TodoWrite is whitelisted in `--allowedTools` because Superpowers workflows expect it. If you remove TodoWrite from the allowed list, subagent-driven-development tasks will complain.
- `--interactive` requires a real TTY. Running it inside a non-interactive subprocess or through a pipe will hit EOF on `input()`. In that case the orchestrator exits with `EOFError`.

## Tuning

Edit the `superpowers_injection` block in `cc_workflows.py` to add new keyword→skill mappings. Keep each injection under 300 chars to avoid polluting context.
