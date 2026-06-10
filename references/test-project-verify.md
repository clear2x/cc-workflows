# test_project 全模式验证记录

项目路径：`/Users/clear2x/hermes_ws/test_project`
验证时间：2025-06-09
脚本版本：cc_workflows.py（含 worktree 默认开启 + loop 分段修复）

---

## 模式 1: agents

```bash
python3 cc_workflows.py agents
```

结果：✅ 列出 8 个可用 agent（claude, Explore, gen-video-qa, gen-video-reviewer, general-purpose, Plan, search-agent, statusline-setup）

---

## 模式 2: run

```bash
python3 cc_workflows.py run "Say: MODE2_RUN_OK" --agent Explore
```

结果：✅ 单 agent 执行成功，model 正确显示（step-3.5-flash-2603）

---

## 模式 3: pipeline

```bash
python3 cc_workflows.py pipeline \
  --step "List all Python files" --agent Explore \
  --step "Read calculator.py and summarize" --agent Explore \
  --step "Identify bugs" --agent general-purpose
```

结果：✅ 3 步流水线全部完成，累计 7 轮，$0.1362

---

## 模式 4: branch（条件分支）

```bash
python3 cc_workflows.py branch \
  --step "Count HIGH severity bugs. Output: bugs_found = <number>" --agent Explore \
  --step "Report bug count" --agent general-purpose \
  --step "Fix plan (execute if bugs found)" --agent general-purpose \
  --step "Skip (execute if no bugs)" --agent general-purpose \
  --if "bugs_found > 0" --then-step 3 --else-step 4
```

结果：✅ 条件判断正确（`bugs_found = 1` → 执行 Step 3 修复方案）

修复点：`evaluate_condition` 现在会从 `last_output` 用正则提取 `key = <number>`，不再只查 context 字典。

---

## 模式 5: parallel（默认 worktree）

```bash
python3 cc_workflows.py parallel \
  --task "Analyze calculator.py" --agent Explore --name calc \
  --task "Analyze logger.py" --agent Explore --name logger
```

结果：✅ 两个任务并发成功，各自创建独立 worktree，自动清理

---

## 模式 6: loop（多步分段 + 断点续接）

```bash
# 4 步连续执行
python3 cc_workflows.py loop "Step 1: list files
Step 2: read calculator.py
Step 3: read logger.py
Step 4: report" --max-steps 4
```

结果：✅ 4 步全部完成，每步独立执行，累计 7 轮

```bash
# 断点续接测试：先跑 2 步
python3 cc_workflows.py loop "..." --max-steps 2
# 再跑 2 步续接
python3 cc_workflows.py loop "..." --max-steps 2
```

结果：✅ 第二次从 Step 3 继续，全部完成

修复点：loop 模式现在按换行拆分 prompt 为独立步骤，每段执行一步；状态保存 `remaining_steps`，支持断点续接。
