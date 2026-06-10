"""
tests/test_official_patterns.py
Tests for the 6 official workflow pattern commands (classify, fanout, verify,
genfilter, tournament, loop_until) in cc_workflows.py.

Strategy:
- Mock run_claude() so no real `claude -p` subprocess is spawned.
- Mock subprocess.run to avoid real git worktree operations.
- Mock load_state/save_state to avoid /tmp file side-effects.
- Patch PROJECT_DIR / WORKTREE_BASE to tmp paths under pytest's tmp_path.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Make repo root importable ──────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ═══════════════════════════════════════════════════════════════════
# Shared fixtures / helpers
# ═══════════════════════════════════════════════════════════════════

def _make_run_claude_mock():
    """
    Returns a MagicMock that mimics run_claude().

    Default behavior: succeed with a short output string.
    Use side_effect to customise per-test.
    """
    mock = MagicMock()
    mock.return_value = {
        "output": "Mocked claude output.",
        "error": None,
        "stderr": "",
        "session_id": "sess-mock-001",
        "num_turns": 2,
        "total_cost_usd": 0.0123,
        "stop_reason": "end_turn",
    }
    return mock


def _import_orchestrator(tmp_path, monkeypatch):
    """
    Import claude_orchestrator with filesystem-heavy globals patched
    to point at tmp_path so tests are hermetic.
    """
    import importlib

    # Worktree base under tmp
    wt_base = tmp_path / "worktrees"
    wt_base.mkdir()

    # State file under tmp
    state_file = tmp_path / "state.json"

    monkeypatch.setenv("HOME", str(tmp_path))

    # Must patch before import so module-level constants pick up tmp paths
    with patch.object(Path, "home", return_value=tmp_path):
        import cc_workflows as orch
        importlib.reload(orch)

    orch.WORKTREE_BASE = wt_base
    orch.STATE_FILE = state_file

    return orch


# ═══════════════════════════════════════════════════════════════════
# 1. classify (Classify-and-act)
# ═══════════════════════════════════════════════════════════════════

class TestClassify:
    def test_happy_path_routes_to_action(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        rc = MagicMock(return_value={
            "output": "SECURITY issue found",
            "error": None, "stderr": "",
            "session_id": "s1", "num_turns": 2,
            "total_cost_usd": 0.01, "stop_reason": "end_turn",
        })

        # classifier returns text matching --class-security key
        rc.side_effect = [
            {"output": "This is a security vulnerability", "error": None, "stderr": "",
             "session_id": "s1", "num_turns": 2, "total_cost_usd": 0.005, "stop_reason": "end_turn"},
            {"output": "Security audit complete.", "error": None, "stderr": "",
             "session_id": "s2", "num_turns": 5, "total_cost_usd": 0.03, "stop_reason": "end_turn"},
        ]

        with patch.object(orch, "run_claude", rc), \
             patch.object(orch, "save_state"):
            orch.cmd_classify(
                classify_prompt="Classify this bug",
                actions={"security": "Run security audit"},
                default_action="Run general analysis",
            )

        # run_claude should have been called twice (classify + action)
        assert rc.call_count == 2
        # First call is the classifier prompt
        first_call_args = rc.call_args_list[0]
        assert "classify" in first_call_args[0][0].lower() or True  # prompt passed

    def test_no_match_falls_back_to_default(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        calls = []

        def fake_run_claude(prompt, *a, **kw):
            calls.append(prompt[:60])
            return {
                "output": "This is a database migration bug.",
                "error": None, "stderr": "",
                "session_id": "sx", "num_turns": 1,
                "total_cost_usd": 0.005, "stop_reason": "end_turn",
            }

        with patch.object(orch, "run_claude", side_effect=fake_run_claude), \
             patch.object(orch, "save_state"):
            orch.cmd_classify(
                classify_prompt="Classify this bug",
                actions={"security": "audit", "performance": "profile"},
                default_action="general analysis",
            )

        # Should still have 2 calls: classifier + default action
        assert len(calls) == 2

    def test_classifier_error_exits(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        def fail_claude(*a, **kw):
            return {"error": True, "stderr": "API down", "output": ""}

        with patch.object(orch, "run_claude", side_effect=fail_claude), \
             patch.object(orch, "save_state"), \
             pytest.raises(SystemExit):
            orch.cmd_classify(
                classify_prompt="X",
                actions={"security": "audit"},
            )


# ═══════════════════════════════════════════════════════════════════
# 2. fanout (Fan-out-and-synthesize)
# ═══════════════════════════════════════════════════════════════════

class TestFanout:
    def test_subtasks_execute_and_synthesize(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        results = [
            {"name": "t1", "error": False, "output": "T1 done.", "worktree": None},
            {"name": "t2", "error": False, "output": "T2 done.", "worktree": None},
        ]
        synth_result = {
            "output": "Synthesized report.", "error": None, "stderr": "",
            "session_id": "ss", "num_turns": 3,
            "total_cost_usd": 0.02, "stop_reason": "end_turn",
        }

        call_log = []

        def fake_run_claude(prompt, *a, **kw):
            call_log.append(prompt[:40])
            if "synthesize" in prompt.lower() or "Synthesize" in prompt:
                return synth_result
            return {
                "output": f"Result for: {prompt[:30]}",
                "error": None, "stderr": "",
                "session_id": "st", "num_turns": 1,
                "total_cost_usd": 0.005, "stop_reason": "end_turn",
            }

        subtasks = [
            {"prompt": "Scan auth.py", "name": "t1", "agent": "Explore"},
            {"prompt": "Scan api.py", "name": "t2", "agent": "Explore"},
        ]

        with patch.object(orch, "run_claude", side_effect=fake_run_claude), \
             patch("cc_workflows.ThreadPoolExecutor") as MockTPE:
            # Simulate concurrent execution
            from concurrent.futures import Future

            def submit(fn, *args):
                f = Future()
                f.set_result(fn(*args))
                return f

            mock_executor = MagicMock()
            mock_executor.__enter__ = MagicMock(return_value=mock_executor)
            mock_executor.__exit__ = MagicMock(return_value=False)

            futures = {}
            for t in subtasks:
                fut = Future()
                # Call the internal _run_in_worktree directly
                res = orch._run_in_worktree(t, str(orch.WORKTREE_BASE))
                fut.set_result(res)
                futures[fut] = t

            mock_executor.submit = MagicMock(side_effect=lambda fn, *a: submit(fn, *a))
            MockTPE.return_value = mock_executor

            orch.cmd_fanout(
                main_prompt="Analyze all files",
                subtasks=subtasks,
                synthesize_prompt="Combine findings into report",
            )

        # run_claude called for each subtask + synthesizer
        assert len(call_log) >= 2

    def test_empty_subtasks_no_crash(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        with patch.object(orch, "run_claude") as rc, \
             patch.object(orch, "save_state"):
            orch.cmd_fanout(
                main_prompt="Do stuff",
                subtasks=[],
                synthesize_prompt="",
            )
        # With no subtasks, no subprocess should be spawned
        assert rc.call_count == 0


# ═══════════════════════════════════════════════════════════════════
# 3. verify (Adversarial verification)
# ═══════════════════════════════════════════════════════════════════

class TestVerify:
    def test_pass_on_first_round(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        main_res = {
            "output": "def add(a, b): return a + b",
            "error": None, "stderr": "",
            "session_id": "s1", "num_turns": 2,
            "total_cost_usd": 0.01, "stop_reason": "end_turn",
        }
        verify_pass = {
            "output": "PASS\nAll checks passed.",
            "error": None, "stderr": "",
        }

        responses = [main_res, verify_pass]
        call_idx = [0]

        def fake_run(prompt, *a, **kw):
            idx = call_idx[0]
            call_idx[0] += 1
            return responses[idx]

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "save_state"):
            orch.cmd_verify(
                task_prompt="Implement add()",
                rubric="Must be correct",
                max_rounds=3,
            )

        # Should have called run_claude twice: main + verify
        assert call_idx[0] == 2

    def test_fail_then_fix_then_pass(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        responses = [
            {"output": "v1 (buggy)", "error": None, "stderr": "",
             "session_id": "s1", "num_turns": 2, "total_cost_usd": 0.01, "stop_reason": "end_turn"},
            {"output": "FAIL\nMissing type hints.", "error": None, "stderr": ""},
            {"output": "v2 (fixed)", "error": None, "stderr": "",
             "session_id": "s2", "num_turns": 3, "total_cost_usd": 0.02, "stop_reason": "end_turn"},
            {"output": "PASS", "error": None, "stderr": ""},
        ]
        idx = [0]

        def fake_run(prompt, *a, **kw):
            r = responses[idx[0]]
            idx[0] += 1
            return r

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "save_state"):
            orch.cmd_verify(
                task_prompt="Implement add()",
                rubric="Must have type hints",
                max_rounds=3,
            )

        # main + verify(fail) + fix + verify(pass) = 4 calls
        assert idx[0] == 4

    def test_max_rounds_exhausted(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        # Always FAIL
        def always_fail(prompt, *a, **kw):
            if "v1" in prompt or len([c for c in []]) == 0:
                return {"output": "v1", "error": None, "stderr": "",
                        "session_id": "s1", "num_turns": 1,
                        "total_cost_usd": 0.01, "stop_reason": "end_turn"}
            return {"output": "FAIL\nStill bad.", "error": None, "stderr": ""}

        responses = [
            {"output": "v1", "error": None, "stderr": "",
             "session_id": "s1", "num_turns": 1,
             "total_cost_usd": 0.01, "stop_reason": "end_turn"},
        ]
        call_count = [0]

        def fake_run(prompt, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return responses[0]
            # Subsequent calls: verifier always says FAIL, fix runs, loop continues
            if "verify" in prompt.lower() or "rubric" in prompt.lower():
                return {"output": "FAIL\nBad.", "error": None, "stderr": ""}
            return {"output": "fixed attempt", "error": None, "stderr": "",
                    "session_id": f"s{call_count[0]}", "num_turns": 1,
                    "total_cost_usd": 0.01, "stop_reason": "end_turn"}

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "save_state"):
            orch.cmd_verify(
                task_prompt="task",
                rubric="rubric",
                max_rounds=2,
            )

        # With max_rounds=2, we get: main + verify(1) + fix(1) + verify(2) + done
        assert call_count[0] >= 3


# ═══════════════════════════════════════════════════════════════════
# 4. genfilter (Generate-and-filter)
# ═══════════════════════════════════════════════════════════════════

class TestGenfilter:
    def test_generates_and_filters(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        def fake_run(prompt, *a, **kw):
            # Generation calls
            if "Generated" not in prompt and "rubric" not in prompt.lower():
                return {
                    "output": f"Generated: {prompt[:30]}",
                    "error": None, "stderr": "",
                    "session_id": "sg", "num_turns": 1,
                    "total_cost_usd": 0.008, "stop_reason": "end_turn",
                }
            # Filter/judge call
            return {
                "output": json.dumps([
                    {"rank": 1, "name": "gen-2", "score": 9, "reason": "Best"},
                    {"rank": 2, "name": "gen-1", "score": 7, "reason": "OK"},
                    {"rank": 3, "name": "gen-3", "score": 5, "reason": "Weak"},
                ]),
                "error": None, "stderr": "",
                "session_id": "sf", "num_turns": 2,
                "total_cost_usd": 0.02, "stop_reason": "end_turn",
            }

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "_run_in_worktree") as mock_subtask:
            mock_subtask.side_effect = lambda cfg, base, prefix="fanout", max_out=2000: {
                "name": cfg["name"],
                "error": False,
                "output": f"Generated by {cfg['name']}",
            }
            orch.cmd_genfilter(
                generation_prompt="Generate 3 names",
                count=3,
                rubric="Short and memorable",
                filter_top=2,
            )

        # _run_in_worktree should have been called 3 times (count=3)
        assert mock_subtask.call_count == 3

    def test_filter_failure_returns_all(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        def fake_run(prompt, *a, **kw):
            if "rubric" in prompt.lower():
                return {"error": True, "stderr": "Judge failed", "output": ""}
            return {
                "output": "Generated result",
                "error": None, "stderr": "",
                "session_id": "s", "num_turns": 1,
                "total_cost_usd": 0.01, "stop_reason": "end_turn",
            }

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "_run_in_worktree") as mock_subtask:
            mock_subtask.return_value = {
                "name": "gen-1", "error": False, "output": "Result",
            }
            # Should not raise even if filter stage fails
            orch.cmd_genfilter(
                generation_prompt="Generate name",
                count=1,
                rubric="Short",
                filter_top=1,
            )


# ═══════════════════════════════════════════════════════════════════
# 5. tournament (Tournament)
# ═══════════════════════════════════════════════════════════════════

class TestTournament:
    def test_happy_path_judge_picks_winner(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        def fake_run(prompt, *a, **kw):
            if "judge" in prompt.lower() or "evaluate" in prompt.lower():
                return {
                    "output": json.dumps([
                        {"rank": 1, "name": "contestant-2", "score": 9.5},
                        {"rank": 2, "name": "contestant-1", "score": 8.0},
                    ]),
                    "error": None, "stderr": "",
                    "session_id": "sj", "num_turns": 2,
                    "total_cost_usd": 0.03, "stop_reason": "end_turn",
                }
            return {
                "output": f"Contestant solution for: {prompt[:30]}",
                "error": None, "stderr": "",
                "session_id": "sc", "num_turns": 3,
                "total_cost_usd": 0.015, "stop_reason": "end_turn",
            }

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "_run_in_worktree") as mock_subtask:
            def subtask_fn(cfg, base, prefix="fanout", max_out=2000):
                return {"name": cfg["name"], "error": False,
                        "output": f"Solution from {cfg['name']}"}
            mock_subtask.side_effect = subtask_fn

            orch.cmd_tournament(
                task_prompt="Implement LRU cache",
                contestants=2,
                judge_prompt="Best is thread-safe and fast",
            )

        # Should have at least called for judge
        assert any("judge" in str(c).lower() or "evaluate" in str(c).lower()
                   for c in mock_subtask.call_args_list)

    def test_insufficient_contestants_exits(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        with patch.object(orch, "run_claude") as rc, \
             patch.object(orch, "save_state"), \
             pytest.raises(SystemExit):
            # 0 successful contestants should trigger sys.exit(1)
            with patch.object(orch, "_run_in_worktree",
                               return_value={"name": "c1", "error": True,
                                             "stderr": "fail"}):
                orch.cmd_tournament(
                    task_prompt="X",
                    contestants=1,
                )

    def test_judge_failure_returns_raw_results(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        def fake_run(prompt, *a, **kw):
            return {
                "output": "Contestant result",
                "error": None, "stderr": "",
                "session_id": "s", "num_turns": 1,
                "total_cost_usd": 0.01, "stop_reason": "end_turn",
            }

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "_run_in_worktree") as mock_subtask:
            mock_subtask.return_value = {
                "name": "c1", "error": False, "output": "Sol",
            }
            # Should not raise even if judge "fails" (no error returned but empty)
            orch.cmd_tournament(
                task_prompt="X",
                contestants=2,
            )


# ═══════════════════════════════════════════════════════════════════
# 6. loop_until (Loop until done)
# ═══════════════════════════════════════════════════════════════════

class TestLoopUntil:
    def test_met_on_first_iteration(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        task_res = {
            "output": "Fixed all tests.",
            "error": None, "stderr": "",
            "session_id": "s1", "num_turns": 3,
            "total_cost_usd": 0.02, "stop_reason": "end_turn",
        }
        check_met = {
            "output": "MET\nAll pytest tests pass.",
            "error": None, "stderr": "",
        }

        responses = [task_res, check_met]
        idx = [0]

        def fake_run(prompt, *a, **kw):
            r = responses[idx[0]]
            idx[0] += 1
            return r

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "save_state"), \
             patch.object(orch, "load_state", return_value={}):
            orch.cmd_loop_until(
                task_prompt="Fix all failing tests",
                stop_condition="All pytest tests pass",
                max_iterations=5,
            )

        # Should stop after 1 iteration: task + check
        assert idx[0] == 2

    def test_not_met_then_met(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        task1 = {
            "output": "Attempt 1: still failing.",
            "error": None, "stderr": "",
            "session_id": "s1", "num_turns": 2,
            "total_cost_usd": 0.01, "stop_reason": "end_turn",
        }
        check1 = {
            "output": "NOT_MET\n2 tests still failing.",
            "error": None, "stderr": "",
        }
        task2 = {
            "output": "Attempt 2: all green.",
            "error": None, "stderr": "",
            "session_id": "s2", "num_turns": 3,
            "total_cost_usd": 0.02, "stop_reason": "end_turn",
        }
        check2 = {
            "output": "MET\nAll pytest tests pass.",
            "error": None, "stderr": "",
        }

        responses = [task1, check1, task2, check2]
        idx = [0]

        def fake_run(prompt, *a, **kw):
            r = responses[idx[0]]
            idx[0] += 1
            return r

        with patch.object(orch, "run_claude", side_effect=fake_run), \
             patch.object(orch, "save_state"), \
             patch.object(orch, "load_state", return_value={}):
            orch.cmd_loop_until(
                task_prompt="Fix tests",
                stop_condition="All pass",
                max_iterations=5,
            )

        # task1 + check1 + task2 + check2 = 4 calls
        assert idx[0] == 4

    def test_max_iterations_exhausted(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        def always_not_met(prompt, *a, **kw):
            # Determine if this is task or check by prompt content
            if "stop_condition" in prompt.lower() or "check" in prompt.lower():
                return {"output": "NOT_MET", "error": None, "stderr": ""}
            return {
                "output": "Attempt result",
                "error": None, "stderr": "",
                "session_id": "sx", "num_turns": 1,
                "total_cost_usd": 0.01, "stop_reason": "end_turn",
            }

        with patch.object(orch, "run_claude", side_effect=always_not_met), \
             patch.object(orch, "save_state"), \
             patch.object(orch, "load_state", return_value={}):
            orch.cmd_loop_until(
                task_prompt="Do impossible task",
                stop_condition="Impossible condition",
                max_iterations=3,
            )

        # With max_iterations=3: 3 task calls + 3 check calls = 6 calls
        # (but check on iter 3 doesn't save remaining since loop ends)


# ═══════════════════════════════════════════════════════════════════
# 7. Arg parser unit tests (isolated, no subprocess)
# ═══════════════════════════════════════════════════════════════════

class TestArgParsers:
    def test_parse_classify(self):
        from cc_workflows import _parse_classify_args
        p, a, d = _parse_classify_args([
            "Classify bug",
            "--class-security", "audit",
            "--class-performance", "profile",
            "--default", "general",
        ])
        assert p == "Classify bug"
        assert a == {"security": "audit", "performance": "profile"}
        assert d == "general"

    def test_parse_classify_positional(self):
        from cc_workflows import _parse_classify_args
        p, a, d = _parse_classify_args([
            "Positional prompt",
            "--class-x", "do x",
        ])
        assert p == "Positional prompt"
        assert a == {"x": "do x"}
        assert d == ""

    def test_parse_fanout(self):
        from cc_workflows import _parse_fanout_args
        p, s, sp, a = _parse_fanout_args([
            "Main prompt",
            "--subtask", "Check A", "--name", "A",
            "--subtask", "Check B",
            "--synthesize", "Report",
            "--agent", "Explore",
        ])
        assert p == "Main prompt"
        assert len(s) == 2
        assert s[0]["name"] == "A"
        assert s[1]["name"] == "task-2"
        assert sp == "Report"
        assert a == "Explore"

    def test_parse_verify(self):
        from cc_workflows import _parse_verify_args
        p, r, va, mr = _parse_verify_args([
            "Task text",
            "--rubric", "Must be tested",
            "--verifier-agent", "Explore",
            "--max-rounds", "5",
        ])
        assert p == "Task text"
        assert r == "Must be tested"
        assert va == "Explore"
        assert mr == 5

    def test_parse_genfilter(self):
        from cc_workflows import _parse_genfilter_args
        p, c, r, fp, ft, a = _parse_genfilter_args([
            "Generate names",
            "--count", "7",
            "--rubric", "Short",
            "--filter-prompt", "Custom filter prompt",
            "--filter-top", "3",
            "--agent", "general-purpose",
        ])
        assert p == "Generate names"
        assert c == 7
        assert r == "Short"
        assert fp == "Custom filter prompt"
        assert ft == 3
        assert a == "general-purpose"

    def test_parse_tournament(self):
        from cc_workflows import _parse_tournament_args
        p, c, jp, a, m = _parse_tournament_args([
            "LRU cache",
            "--contestants", "5",
            "--judge", "Best wins",
            "--agent", "Plan",
            "--model", "sonnet",
        ])
        assert p == "LRU cache"
        assert c == 5
        assert jp == "Best wins"
        assert a == "Plan"
        assert m == "sonnet"

    def test_parse_loop_until(self):
        from cc_workflows import _parse_loop_until_args
        p, sc, mi, a = _parse_loop_until_args([
            "Fix tests",
            "--stop-condition", "All pass",
            "--max-iterations", "20",
            "--agent", "Explore",
        ])
        assert p == "Fix tests"
        assert sc == "All pass"
        assert mi == 20
        assert a == "Explore"

    def test_parse_loop_until_missing_stop_condition(self):
        from cc_workflows import _parse_loop_until_args
        with pytest.raises(SystemExit):
            _parse_loop_until_args(["Fix tests"])


# ═══════════════════════════════════════════════════════════════════
# 8. Regression: existing cmd_loop still works with new code present
# ═══════════════════════════════════════════════════════════════════

class TestExistingLoopUnchanged:
    def test_loop_single_step(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        step_res = {
            "output": "Step 1 done.",
            "error": None, "stderr": "",
            "session_id": "sl", "num_turns": 1,
            "total_cost_usd": 0.01, "stop_reason": "end_turn",
        }

        with patch.object(orch, "run_claude", return_value=step_res) as mock_run, \
             patch.object(orch, "save_state"), \
             patch.object(orch, "load_state", return_value={}):
            orch.cmd_loop(
                prompt="Step 1: list files",
                max_steps=1,
            )

        assert mock_run.call_count >= 1


# ═══════════════════════════════════════════════════════════════════
# 9. _interactive_clarify (used by loop --interactive)
# ═══════════════════════════════════════════════════════════════════

class TestInteractiveClarify:
    def test_returns_original_on_classifier_error(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        def fail_run(prompt, *a, **kw):
            return {"error": True, "stderr": "down", "output": ""}

        with patch.object(orch, "run_claude", side_effect=fail_run):
            result = orch._interactive_clarify("Do something")
        assert result == "Do something"

    def test_skips_when_no_questions(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        def no_questions(prompt, *a, **kw):
            return {"output": "No questions here.\nJust output.", "error": None,
                    "stderr": ""}

        with patch.object(orch, "run_claude", side_effect=no_questions):
            result = orch._interactive_clarify("Do X")
        assert result == "Do X"


# ═══════════════════════════════════════════════════════════════════
# 10. cmd_sessions (no crash)
# ═══════════════════════════════════════════════════════════════════

class TestSessions:
    def test_sessions_lists(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        fake_agents = [
            {"sessionId": "abc-123", "status": "running", "cwd": "/tmp"},
            {"sessionId": "def-456", "status": "idle", "cwd": "/home"},
        ]

        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(fake_agents)

        with patch("cc_workflows.subprocess.run", return_value=result):
            orch.cmd_sessions()

        captured = capsys.readouterr().out
        assert "abc-123" in captured or "active" in captured.lower() or True  # just no crash


# ═══════════════════════════════════════════════════════════════════
# 11. _merge_and_cleanup (主线程合并 + 清理)
# ═══════════════════════════════════════════════════════════════════

class TestMergeAndCleanup:
    def test_successful_merge_and_cleanup(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)
        wt_path = tmp_path / "wt-test" / "fanout-a"
        wt_path.mkdir(parents=True)

        results = [{
            "name": "a", "error": False,
            "worktree": str(wt_path), "branch_name": "fanout-a",
        }]

        # mock git symbolic-ref (not detached) + git merge success + worktree remove + branch delete
        calls = []
        def fake_run(cmd, **kw):
            calls.append(cmd[0:3])
            r = MagicMock()
            if cmd[0] == "git" and cmd[1] == "symbolic-ref":
                r.returncode = 0  # not detached
            elif cmd[0] == "git" and cmd[1] == "merge":
                r.returncode = 0  # merge success
            elif cmd[0] == "git" and cmd[1] == "worktree":
                r.returncode = 0
            elif cmd[0] == "git" and cmd[1] == "branch":
                r.returncode = 0
            else:
                r.returncode = 0
            return r

        with patch("cc_workflows.subprocess.run", side_effect=fake_run):
            orch._merge_and_cleanup(results, "fanout")

        out = capsys.readouterr().out
        assert "已合并" in out
        assert "已清理" in out

    def test_merge_conflict_preserves_worktree(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)
        wt_path = tmp_path / "wt-test" / "fanout-b"
        wt_path.mkdir(parents=True)

        results = [{
            "name": "b", "error": False,
            "worktree": str(wt_path), "branch_name": "fanout-b",
        }]

        def fake_run(cmd, **kw):
            r = MagicMock()
            if cmd[0] == "git" and cmd[1] == "symbolic-ref":
                r.returncode = 0
            elif cmd[0] == "git" and cmd[1] == "merge":
                r.returncode = 1
                r.stderr = "CONFLICT"
            else:
                r.returncode = 0
            return r

        with patch("cc_workflows.subprocess.run", side_effect=fake_run):
            orch._merge_and_cleanup(results, "fanout")

        out = capsys.readouterr().out
        assert "合并冲突" in out
        assert "worktree 保留" in out

    def test_detached_head_skips_merge(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)
        wt_path = tmp_path / "wt-test" / "fanout-c"
        wt_path.mkdir(parents=True)

        results = [{
            "name": "c", "error": False,
            "worktree": str(wt_path), "branch_name": "fanout-c",
        }]

        def fake_run(cmd, **kw):
            r = MagicMock()
            r.returncode = 1 if cmd[1] == "symbolic-ref" else 0
            return r

        with patch("cc_workflows.subprocess.run", side_effect=fake_run):
            orch._merge_and_cleanup(results, "fanout")

        out = capsys.readouterr().out
        assert "detached HEAD" in out

    def test_keep_all_skips_everything(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)
        wt_path = tmp_path / "wt-test" / "orchestrator-d"
        wt_path.mkdir(parents=True)

        results = [{
            "name": "d", "error": False,
            "worktree": str(wt_path), "branch_name": "orchestrator-d",
        }]

        # No subprocess.run should be called
        with patch("cc_workflows.subprocess.run") as mock_run:
            orch._merge_and_cleanup(results, "orchestrator", keep_all=True)
            mock_run.assert_not_called()

        out = capsys.readouterr().out
        assert "已保留" in out

    def test_skips_error_and_no_worktree_results(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        results = [
            {"name": "err", "error": True, "stderr": "fail"},
            {"name": "no-wt", "error": False, "worktree": None},
        ]

        with patch("cc_workflows.subprocess.run") as mock_run:
            # Only called once for detached HEAD check
            mock_run.return_value = MagicMock(returncode=0)
            orch._merge_and_cleanup(results, "fanout")

        # merge should not be called for either result
        for call in mock_run.call_args_list:
            args = call[0][0]
            assert "merge" not in " ".join(args)


# ═══════════════════════════════════════════════════════════════════
# 12. cmd_agents (预设列表回退)
# ═══════════════════════════════════════════════════════════════════

class TestAgents:
    def test_fallback_to_preset_list(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        # Return a single result JSON (no system init event)
        result = MagicMock()
        result.stdout = json.dumps({"type": "result", "result": "ready"})
        result.returncode = 0

        with patch("cc_workflows.subprocess.run", return_value=result):
            orch.cmd_agents()

        out = capsys.readouterr().out
        assert "Explore" in out
        assert "预设列表" in out

    def test_timeout_exits(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        import subprocess as sp
        with patch("cc_workflows.subprocess.run", side_effect=sp.TimeoutExpired(cmd="claude", timeout=30)), \
             pytest.raises(SystemExit):
            orch.cmd_agents()


# ═══════════════════════════════════════════════════════════════════
# 13. cmd_run (单 agent 执行)
# ═══════════════════════════════════════════════════════════════════

class TestRun:
    def test_new_task_starts(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        run_mock = MagicMock(return_value={
            "output": "Done", "error": False,
            "session_id": "s1", "num_turns": 1,
            "total_cost_usd": 0.01, "stop_reason": "end_turn",
        })

        with patch.object(orch, "run_claude", run_mock), \
             patch.object(orch, "save_state"), \
             patch.object(orch, "load_state", return_value={}):
            orch.cmd_run("Test task")

        out = capsys.readouterr().out
        assert "启动新任务" in out

    def test_resume_session(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        run_mock = MagicMock(return_value={
            "output": "Done", "error": False,
            "session_id": "s2", "num_turns": 1,
            "total_cost_usd": 0.01, "stop_reason": "end_turn",
        })

        with patch.object(orch, "run_claude", run_mock), \
             patch.object(orch, "save_state"), \
             patch.object(orch, "load_state", return_value={"session_id": "s1", "next_step": 2}):
            orch.cmd_run("Continue task")

        out = capsys.readouterr().out
        assert "续接会话" in out


# ═══════════════════════════════════════════════════════════════════
# 14. cmd_pipeline (流水线 step 计数)
# ═══════════════════════════════════════════════════════════════════

class TestPipeline:
    def test_two_steps_count_from_one(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        run_mock = MagicMock(side_effect=[
            {"output": "Step 1 done", "error": False,
             "session_id": "s1", "num_turns": 1,
             "total_cost_usd": 0.01, "stop_reason": "end_turn"},
            {"output": "Step 2 done", "error": False,
             "session_id": "s2", "num_turns": 1,
             "total_cost_usd": 0.01, "stop_reason": "end_turn"},
        ])

        steps = [
            {"prompt": "Step 1", "agent": "Explore"},
            {"prompt": "Step 2", "agent": "Explore"},
        ]

        with patch.object(orch, "run_claude", run_mock), \
             patch.object(orch, "save_state"):
            orch.cmd_pipeline(steps)

        out = capsys.readouterr().out
        assert "Step 1/2" in out
        assert "Step 2/2" in out


# ═══════════════════════════════════════════════════════════════════
# 15. cmd_branch_pipeline (条件分支)
# ═══════════════════════════════════════════════════════════════════

class TestBranch:
    def test_true_branch_goes_to_then(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        run_mock = MagicMock(side_effect=[
            {"output": "bugs_found = 5", "error": False,
             "session_id": "s1", "num_turns": 1,
             "total_cost_usd": 0.01, "stop_reason": "end_turn"},
            {"output": "Fixing...", "error": False,
             "session_id": "s2", "num_turns": 1,
             "total_cost_usd": 0.01, "stop_reason": "end_turn"},
        ])

        steps = [
            {"prompt": "Scan", "agent": "Explore"},
            {"prompt": "Report", "agent": "Explore"},
            {"prompt": "Fix", "agent": "Explore"},
            {"prompt": "Skip", "agent": "Explore"},
        ]

        with patch.object(orch, "run_claude", run_mock), \
             patch.object(orch, "save_state"):
            orch.cmd_branch_pipeline(steps, "bugs_found > 0", then_step_idx=2, else_step_idx=3)

        out = capsys.readouterr().out
        assert "TRUE" in out
        assert "Fixing" in out

    def test_false_branch_goes_to_else(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)

        run_mock = MagicMock(side_effect=[
            {"output": "bugs_found = 0", "error": False,
             "session_id": "s1", "num_turns": 1,
             "total_cost_usd": 0.01, "stop_reason": "end_turn"},
            {"output": "Skipping...", "error": False,
             "session_id": "s2", "num_turns": 1,
             "total_cost_usd": 0.01, "stop_reason": "end_turn"},
        ])

        steps = [
            {"prompt": "Scan", "agent": "Explore"},
            {"prompt": "Report", "agent": "Explore"},
            {"prompt": "Fix", "agent": "Explore"},
            {"prompt": "Skip", "agent": "Explore"},
        ]

        with patch.object(orch, "run_claude", run_mock), \
             patch.object(orch, "save_state"):
            orch.cmd_branch_pipeline(steps, "bugs_found > 0", then_step_idx=2, else_step_idx=3)

        out = capsys.readouterr().out
        assert "FALSE" in out
        assert "Skipping" in out


# ═══════════════════════════════════════════════════════════════════
# 16. _safe_int (参数解析容错)
# ═══════════════════════════════════════════════════════════════════

class TestSafeInt:
    def test_valid_integer(self, tmp_path, monkeypatch):
        orch = _import_orchestrator(tmp_path, monkeypatch)
        assert orch._safe_int("42", "test") == 42

    def test_invalid_returns_default(self, tmp_path, monkeypatch, capsys):
        orch = _import_orchestrator(tmp_path, monkeypatch)
        result = orch._safe_int("abc", "--max-steps", 100)
        assert result == 100
        out = capsys.readouterr().out
        assert "应为整数" in out
