"""Tests for core/task_manager.py - TaskManager and TaskInfo."""
import time
import pytest
from unittest.mock import MagicMock, patch

from core.task_manager import TaskManager, TaskInfo


# ---------------------------------------------------------------------------
# TaskInfo dataclass
# ---------------------------------------------------------------------------

class TestTaskInfo:
    def test_default_status_is_running(self):
        info = TaskInfo(id=1, name="test")
        assert info.status == "running"

    def test_default_result_is_empty_string(self):
        info = TaskInfo(id=2, name="another")
        assert info.result == ""

    def test_default_steps_is_zero(self):
        info = TaskInfo(id=3, name="steps_test")
        assert info.steps == 0

    def test_created_at_is_recent(self):
        before = time.time()
        info = TaskInfo(id=4, name="time_test")
        after = time.time()
        assert before <= info.created_at <= after

    def test_fields_are_mutable(self):
        info = TaskInfo(id=5, name="mutate")
        info.status = "done"
        info.result = "finished"
        info.steps = 7
        assert info.status == "done"
        assert info.result == "finished"
        assert info.steps == 7


# ---------------------------------------------------------------------------
# TaskManager basic operations
# ---------------------------------------------------------------------------

class TestTaskManagerBasic:
    def test_initial_task_list_is_empty(self):
        mgr = TaskManager()
        assert mgr.list_all() == []

    def test_get_returns_none_for_missing_id(self):
        mgr = TaskManager()
        assert mgr.get(999) is None

    def test_summary_returns_no_tasks_string_when_empty(self):
        mgr = TaskManager()
        summary = mgr.summary()
        assert "没有" in summary or "no" in summary.lower() or summary == ""

    def test_counter_starts_at_zero(self):
        mgr = TaskManager()
        assert mgr._counter == 0


# ---------------------------------------------------------------------------
# TaskManager.launch()
# ---------------------------------------------------------------------------

class TestTaskManagerLaunch:
    def _make_mock_brain(self, step_results=None):
        mock_brain = MagicMock()
        step_results = step_results or [{"done": True, "result": "Task complete"}]
        mock_brain.step.side_effect = step_results + [None] * 10
        mock_brain._append_user = MagicMock()
        return mock_brain

    def test_launch_returns_positive_integer_task_id(self):
        mgr = TaskManager()
        mock_brain = self._make_mock_brain()
        with patch("core.brain.Brain", return_value=mock_brain), \
             patch("actions.executor.BG_TOOLS_SCHEMA", []):
            tid = mgr.launch("test task", "Do something")
        assert isinstance(tid, int)
        assert tid > 0

    def test_launch_increments_task_id_each_call(self):
        mgr = TaskManager()
        mock_brain1 = self._make_mock_brain()
        mock_brain2 = self._make_mock_brain()
        with patch("core.brain.Brain", side_effect=[mock_brain1, mock_brain2]), \
             patch("actions.executor.BG_TOOLS_SCHEMA", []):
            tid1 = mgr.launch("task1", "prompt1")
            tid2 = mgr.launch("task2", "prompt2")
        assert tid2 == tid1 + 1

    def test_launched_task_appears_in_list_all(self):
        mgr = TaskManager()
        mock_brain = self._make_mock_brain()
        with patch("core.brain.Brain", return_value=mock_brain), \
             patch("actions.executor.BG_TOOLS_SCHEMA", []):
            tid = mgr.launch("listed task", "Do work")
        time.sleep(0.1)
        ids = [t.id for t in mgr.list_all()]
        assert tid in ids

    def test_task_completes_with_done_status(self):
        mgr = TaskManager()
        mock_brain = self._make_mock_brain(
            step_results=[{"done": True, "result": "All done!"}]
        )
        with patch("core.brain.Brain", return_value=mock_brain), \
             patch("actions.executor.BG_TOOLS_SCHEMA", []):
            tid = mgr.launch("complete task", "Finish it")

        deadline = time.time() + 3.0
        while time.time() < deadline:
            info = mgr.get(tid)
            if info and info.status == "done":
                break
            time.sleep(0.05)

        info = mgr.get(tid)
        assert info is not None
        assert info.status == "done"
        assert info.result == "All done!"

    def test_on_done_callback_called_after_completion(self):
        mgr = TaskManager()
        mock_brain = self._make_mock_brain(
            step_results=[{"done": True, "result": "callback test"}]
        )
        callback_results = []

        def on_done(info):
            callback_results.append(info)

        with patch("core.brain.Brain", return_value=mock_brain), \
             patch("actions.executor.BG_TOOLS_SCHEMA", []):
            mgr.launch("callback task", "Do it", on_done=on_done)

        deadline = time.time() + 3.0
        while time.time() < deadline and not callback_results:
            time.sleep(0.05)

        assert len(callback_results) == 1
        assert callback_results[0].status == "done"

    def test_exception_in_brain_step_marks_task_failed(self):
        mgr = TaskManager()
        mock_brain = MagicMock()
        mock_brain.step.side_effect = RuntimeError("simulated crash")
        mock_brain._append_user = MagicMock()

        with patch("core.brain.Brain", return_value=mock_brain), \
             patch("actions.executor.BG_TOOLS_SCHEMA", []):
            tid = mgr.launch("failing task", "This will crash")

        deadline = time.time() + 3.0
        while time.time() < deadline:
            info = mgr.get(tid)
            if info and info.status == "failed":
                break
            time.sleep(0.05)

        info = mgr.get(tid)
        assert info.status == "failed"
        assert "simulated crash" in info.result


# ---------------------------------------------------------------------------
# TaskManager.summary()
# ---------------------------------------------------------------------------

class TestTaskManagerSummary:
    def test_summary_includes_task_id(self):
        mgr = TaskManager()
        info = TaskInfo(id=42, name="my_task", status="done", result="finished")
        mgr._tasks[42] = info
        s = mgr.summary()
        assert "42" in s

    def test_summary_includes_task_name(self):
        mgr = TaskManager()
        info = TaskInfo(id=1, name="special_task_name", status="running")
        mgr._tasks[1] = info
        s = mgr.summary()
        assert "special_task_name" in s

    def test_summary_includes_result_for_done_tasks(self):
        mgr = TaskManager()
        info = TaskInfo(id=1, name="result_task", status="done", result="the answer is 42")
        mgr._tasks[1] = info
        s = mgr.summary()
        assert "the answer is 42" in s

    def test_summary_lists_multiple_tasks(self):
        mgr = TaskManager()
        for i in range(3):
            mgr._tasks[i] = TaskInfo(id=i, name=f"task_{i}", status="done", result=f"result_{i}")
        s = mgr.summary()
        for i in range(3):
            assert f"task_{i}" in s
