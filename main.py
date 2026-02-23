import time
import logging
import pyautogui

from config import config

log = logging.getLogger(__name__)
from core.adapter import UniversalLLM
from core.brain import Brain
from actions.executor import SCREENSHOT_PATH


class WorkerLoop:
    def __init__(self, task: str, use_native_tools: bool = True):
        self.task = task
        self.use_native_tools = use_native_tools
        self._init_llms()
        self.brain = Brain(self.primary_llm, use_native_tools)
        self.brain._append_user(f"Task: {task}")
        self.step_count = 0

    def _init_llms(self):
        self.primary_llm = UniversalLLM(
            config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL,
        )
        self.secondary_llm = None
        if config.LLM2_API_BASE and config.LLM2_API_KEY:
            self.secondary_llm = UniversalLLM(
                config.LLM2_API_KEY, config.LLM2_API_BASE, config.LLM2_MODEL,
            )
        self.active_llm = self.primary_llm

    def _failover(self) -> bool:
        if self.secondary_llm and self.active_llm is not self.secondary_llm:
            log.info("[Failover] -> secondary: %s", self.secondary_llm.model)
            self.active_llm = self.secondary_llm
            self.brain.llm = self.secondary_llm
            return True
        return False

    def run_once(self) -> bool:
        """Run one step. Returns False if task is done or model stopped."""
        try:
            result = self.brain.step()
        except Exception as e:
            log.error("[Error] %s", e)
            if self._failover():
                return True
            return False

        if not result:
            return False

        self.step_count += 1
        desc = result.get("result", "")
        log.info("[Step %d] %s", self.step_count, desc)

        if result.get("done"):
            return False

        return True

    def run(self, max_steps: int = 50):
        while self.step_count < max_steps:
            if not self.run_once():
                break
        if self.step_count >= max_steps:
            log.warning("[Warning] Max steps reached")
