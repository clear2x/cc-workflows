# gen-video 独立版编排器

## 背景

`gen-video` 原生的 `workflow.js` 依赖 Claude Code 内部的 `agent()` 函数，无法在 Hermes 或其他宿主环境中直接执行。我们在 `gen-video-orchestrator.py` 中用 `claude -p` 子进程模拟双代理模式，实现了同样的编排逻辑。

## 脚本位置

```
.agents/skills/gen-video/gen-video-orchestrator.py
```

## 与 workflow.js 的对应关系

| workflow.js | gen-video-orchestrator.py |
|---|---|
| `agent(prompt, {model, label})` | `run_claude(prompt, cwd, agent, label)` |
| `agent(prompt, {agentType: 'reviewer'})` | `run_review(prompt, cwd, label)` — 独立 session |
| `phase('Phase N')` | `phase(label)` — 打印分隔符 |
| `while (!passed) { ... if (❌) retry }` | Python while 循环 + `check_contains_fail()` |
| `log()` | `print()` |

## 关键设计决策

1. **独立 session 审查**：`run_review()` 不传入主代理的 `session_id`，确保审查代理看不到主代理的思考过程
2. **❌ 检测**：通过字符串检测判断是否通过，比解析结构化报告更鲁棒
3. **重试策略**：每个 Phase 最多重试 3 次，失败则停止整个工作流
4. **硬编码规格**：duration_min=4, aspect=9:16, cta 等直接写在脚本中，需要时改为从命令行参数读取

## 调用方式

```bash
cd /Users/clear2x/hermes_ws
python3 .agents/skills/gen-video/gen-video-orchestrator.py qwen3-demo
```

产物目录：`videos/qwen3-demo/`

## 已知依赖

- `claude` CLI 可用（路径可能不在 PATH 中，脚本中使用完整路径 `/Users/clear2x/.local/bin/claude`）
- TTS: siliconflow-tts（stepfun-tts 目录不存在，fallback 到 siliconflow）
- 图片生成: ruoli-image-creator
- HyperFrames: `npx hyperframes init`
- AI taste check / narration check 脚本在 `gen-video-script/scripts/`

## 运行时注意事项

- **Python 输出缓冲**：在后台运行（`background=true`）时，必须用 `python3 -u` 或设置 `PYTHONUNBUFFERED=1`，否则 `print()` 输出被缓冲，`process(action='log')` 会看到空输出。前台运行无此问题。
- **`process(action='log')` 空输出诊断**：如果后台任务 running 但 log 为空，通常是 stdout 缓冲导致。杀掉重跑，加 `-u` 参数。
- **`claude` 路径**：如果脚本报 `FileNotFoundError: 'claude'`，说明 `claude` 不在 PATH 中。用 `which claude` 找到完整路径，替换脚本中的 `cmd` 首元素。
