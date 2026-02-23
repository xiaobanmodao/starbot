"""后台任务管理器 — 支持多任务并发执行"""
import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TaskInfo:
    id: int
    name: str
    status: str = "running"
    result: str = ""
    steps: int = 0
    created_at: float = field(default_factory=time.time)


class TaskManager:
    MAX_TASKS = 200          # 最多保留任务数
    TASK_TIMEOUT = 600       # 单任务最长运行秒数

    def __init__(self):
        self._tasks: dict[int, TaskInfo] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def launch(self, name: str, task_prompt: str,
               on_done: Callable | None = None) -> int:
        with self._lock:
            self._counter += 1
            tid = self._counter
            info = TaskInfo(id=tid, name=name)
            self._tasks[tid] = info
            self._cleanup_old()

        def _run():
            from core.brain import Brain
            from actions.executor import get_bg_tools_schema
            brain = Brain(tools_schema=get_bg_tools_schema())
            brain._append_user(f"后台任务: {task_prompt}\n完成后用 done 工具汇报结果。")
            deadline = time.time() + self.TASK_TIMEOUT
            for i in range(50):
                if time.time() > deadline:
                    info.status = "failed"
                    info.result = f"超时（>{self.TASK_TIMEOUT}s）"
                    break
                try:
                    result = brain.step()
                except Exception as e:
                    info.status = "failed"
                    info.result = str(e)
                    break
                if not result:
                    break
                info.steps = i + 1
                if result.get("done"):
                    info.status = "done"
                    info.result = result.get("result", "")
                    break
                if result.get("text"):
                    info.result = result["text"]
                    info.status = "done"
                    break
            else:
                info.status = "done"
                info.result = info.result or "达到最大步数"

            if info.status == "running":
                info.status = "done"
            if on_done:
                on_done(info)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return tid

    def _cleanup_old(self):
        """保留最新 MAX_TASKS 条，超出时删除最旧的已完成任务。"""
        if len(self._tasks) <= self.MAX_TASKS:
            return
        done = sorted(
            [t for t in self._tasks.values() if t.status != "running"],
            key=lambda t: t.created_at
        )
        for t in done[:len(self._tasks) - self.MAX_TASKS]:
            del self._tasks[t.id]

    def get(self, tid: int) -> TaskInfo | None:
        with self._lock:
            return self._tasks.get(tid)

    def list_all(self) -> list[TaskInfo]:
        with self._lock:
            return list(self._tasks.values())

    def summary(self) -> str:
        with self._lock:
            tasks = list(self._tasks.values())
        if not tasks:
            return "没有任务"
        lines = []
        for t in tasks:
            elapsed = int(time.time() - t.created_at)
            icon = {"running": "🔄", "done": "✅", "failed": "❌"}.get(t.status, "?")
            line = f"#{t.id} {icon} {t.name} ({t.steps}步, {elapsed}s)"
            if t.status != "running" and t.result:
                snippet = t.result[:80]
                line += f" → {snippet}{'…' if len(t.result) > 80 else ''}"
            lines.append(line)
        return "\n".join(lines)
