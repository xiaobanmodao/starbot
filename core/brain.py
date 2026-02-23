import json
import re
import base64
import logging

from core.adapter import UniversalLLM
from actions.executor import TOOLS_SCHEMA, SCREENSHOT_PATH, execute
from memory.store import MemoryStore
from config import config

log = logging.getLogger(__name__)

_TOKEN_LIMIT = 30_000
_KEEP_TAIL = 12
_COMPRESS_HEAD = 3
_TOOL_RESULT_MAX = 500

SYSTEM_PROMPT = """你是 Starbot，运行在用户电脑上、通过 Discord 交流的 AI 助手。

## 性格
像朋友一样说话，简洁自然。不说"已为您完成"之类的汇报式语气。

## ★ 任务执行协议（必须遵守）

### 1. 规划 — 复杂任务先分解
凡是涉及 2 步以上操作的任务，**必须先输出编号计划，再开始执行**：
> 好，分三步：① 先查X ② 再做Y ③ 最后验证Z，开始执行……

简单对话/单步操作不需要计划，直接做。

### 2. 迭代 — 失败换方案，不接受烂结果
- 工具调用失败 → 分析原因，换方案重试，**最多尝试 3 种不同方法**
- 结果质量不满足需求 → 调整参数或换工具，不提交低质量结果
- 禁止连续调同一个失败工具超过 2 次，必须先换思路

### 3. 复盘 — 完成后必须回顾
每次多步任务全部完成后，用一段话总结：
> ✅ 完成了什么 / ⚠️ 遇到什么问题怎么解决的 / 📌 值得记住的经验

有价值的经验和踩坑立刻 memory_save（knowledge）。

## 判断逻辑
- 闲聊/问答 → 直接回复，不调用工具
- 需要查资料 → web_search → fetch_page 读原文
- 需要操作电脑 → 调用工具执行
- 不确定屏幕状态 → 先 screenshot

## 屏幕操作
截图上有红色坐标网格（每200px一条线），用网格精确定位坐标。
- 看不清细节：screenshot_region 放大，或 read_screen_text OCR
- 找不到按钮位置：find_image 用模板图匹配，比坐标更可靠
- 需要操作特定窗口：先 window_focus 切换，再操作
- 连续操作有把握时不要每步截图，完成后检查一次

## 工具选择
文件：file_read/write/list/search/delete，压缩用 zip_files/unzip
网络：web_search → fetch_page（读文章）；http_request（调 API/POST）
进程：process_list 查看，process_kill 终止
窗口：window_list 列出，window_focus 切换，window_resize 最大化/最小化，screenshot_window 截取单窗口
系统：get_screen_size 获取分辨率，mouse_position 获取鼠标位置，get_env 读环境变量
注册表：registry_read/write（HKCU/HKLM）
电源：power（shutdown/restart/sleep/lock）
通知：notify 发桌面通知，适合后台任务完成时提醒用户

## 效率原则
- 能批量执行的操作连续调用，减少截图次数
- 先 memory_recall 查相关经验，有经验直接复用
- 任务完成后 memory_save 保存有价值的经验（界面布局、操作流程、踩过的坑）

## 学习策略
上网：web_search → fetch_page 读原文 → 多源交叉验证 → memory_save 结构化笔记
视频：learn_video_plus 学习视频（支持 YouTube/B站等 1000+ 平台，自动字幕+Whisper转写）
保存记忆时：写清楚来源、核心要点、适用场景

## 多任务
耗时任务用 bg_task 放后台，完成后用 notify 提醒用户。用 task_status 查进度。

## 记忆
- memory_save：偏好用 preference，知识/经验用 knowledge
- memory_recall：搜索时用 **2-5 个核心关键词**（不用整句话），搜不到就换同义词再试

## 格式
- 纯文字问答：直接回复，末尾加 ✦，**不调用任何工具（包括 done）**
- 多步操作任务全部完成后才调用 done（result 填一句话结论）
- **严禁**输出纯数字序列（如 1\n2\n3\n...），规划步骤必须用 ①②③ 或 "1. 描述" 格式"""

TEXT_MODE_SUFFIX = """

Since tool calling is not available, respond with a JSON block to invoke a tool:
```json
{"name": "tool_name", "arguments": {...}}
```
Output ONLY the JSON block, no other text."""


class Brain:
    def __init__(self, llm: UniversalLLM | None = None, use_native_tools: bool = True, tools_schema: list | None = None):
        self.llm = llm or UniversalLLM(
            config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL,
        )
        self.use_native_tools = use_native_tools
        self._tools_schema = tools_schema if tools_schema is not None else TOOLS_SCHEMA
        self._memory = MemoryStore()
        # ReAct: track consecutive tool failures for retry hints
        self._fail_streak: int = 0
        # Token usage tracking
        self.usage: dict = {"input": 0, "output": 0, "calls": 0}
        sys_content = SYSTEM_PROMPT if use_native_tools else SYSTEM_PROMPT + TEXT_MODE_SUFFIX
        prefs = self._memory.get_preferences()
        if prefs:
            sys_content += "\n\n## 用户偏好\n" + "\n".join(f"- {p}" for p in prefs)
        self.messages: list[dict] = [{"role": "system", "content": sys_content}]

    # ---- Context compression ----
    def _estimate_tokens(self) -> int:
        """Rough token estimate: ~4 chars per token for text, ~1000 tokens per image."""
        total = 0
        for msg in self.messages:
            c = msg.get("content", "")
            if isinstance(c, str):
                total += len(c) // 4
            elif isinstance(c, list):
                for part in c:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            total += len(part.get("text", "")) // 4
                        elif part.get("type") == "image_url":
                            total += 1000
            elif isinstance(c, dict):
                total += len(json.dumps(c)) // 4
        return total

    def _compress_context(self):
        """Remove old images and trim history when context is too large."""
        if self._estimate_tokens() < _TOKEN_LIMIT:
            return

        # Phase 1: Strip images from all but the last 4 messages
        for msg in self.messages[:-4]:
            c = msg.get("content")
            if isinstance(c, list):
                text_parts = [p for p in c if isinstance(p, dict) and p.get("type") == "text"]
                msg["content"] = text_parts[0].get("text", "") if text_parts else "[image removed]"

        if self._estimate_tokens() < _TOKEN_LIMIT:
            return

        # Phase 2: Truncate long tool results in the middle of history
        for msg in self.messages[2:-6]:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if len(content) > _TOOL_RESULT_MAX:
                    msg["content"] = content[:_TOOL_RESULT_MAX] + "…[truncated]"

        if self._estimate_tokens() < _TOKEN_LIMIT:
            return

        # Phase 3: Keep system + last N messages, but ensure no orphan tool messages
        if len(self.messages) > 15:
            tail = self.messages[-_KEEP_TAIL:]
            # Drop leading tool messages that have no matching assistant tool_call
            while tail and tail[0].get("role") == "tool":
                tail = tail[1:]
            self.messages = self.messages[:_COMPRESS_HEAD] + tail

    def _image_content(self, path: str) -> dict | None:
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        except (FileNotFoundError, OSError):
            return None

    def _append_user(self, text: str, image_path: str | None = None):
        # 首条用户消息时，把相关记忆直接拼入消息，不额外增加消息轮次
        if len(self.messages) == 1 and text and not image_path:
            # 用多关键词策略检索，比单次全文搜索召回率高得多
            relevant = self._memory.search_multi(text, limit=6)
            contents = [r["content"] for r in relevant]
            if contents:
                mem_block = "\n".join(f"- {m[:200]}" for m in contents)
                text = f"[相关记忆]\n{mem_block}\n\n{text}"
        if image_path:
            img = self._image_content(image_path)
            if img:
                self.messages.append({"role": "user", "content": [
                    {"type": "text", "text": text}, img,
                ]})
                return
        self.messages.append({"role": "user", "content": text})

    # ---- Native tool calling mode ----
    def _call_native(self) -> dict | list | None:
        self._compress_context()
        resp = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=self.messages,
            tools=self._tools_schema,
        )
        if not resp.choices:
            return None
        # Track token usage
        if resp.usage:
            self.usage["input"] += resp.usage.prompt_tokens or 0
            self.usage["output"] += resp.usage.completion_tokens or 0
            self.usage["calls"] += 1
        msg = resp.choices[0].message
        self.messages.append(msg.model_dump(exclude_none=True))
        if msg.tool_calls:
            actions = [{"name": tc.function.name, "arguments": tc.function.arguments, "id": tc.id}
                       for tc in msg.tool_calls]
            return actions if len(actions) > 1 else actions[0]
        if msg.content:
            return {"text": msg.content}
        return None

    def _call_native_stream(self, on_chunk=None, on_clear=None) -> dict | None:
        """Stream version of _call_native. Calls on_chunk(text) with each text delta.
        Calls on_clear() once when tool calls are first detected (LLM switched from
        text to tool-call mode — previously streamed text was just internal planning).
        Returns list of tool calls or single text action."""
        self._compress_context()
        stream = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=self.messages,
            tools=self._tools_schema,
            stream=True,
        )
        full_text = ""
        tool_calls: dict[int, dict] = {}
        _tool_call_signalled = False   # 只触发一次 on_clear

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                full_text += delta.content
                if on_chunk:
                    on_chunk(delta.content)

            if delta.tool_calls:
                # 第一次检测到工具调用：通知调用方清除已流式显示的草稿文字
                if not _tool_call_signalled:
                    _tool_call_signalled = True
                    if on_clear:
                        on_clear()
                for tc in delta.tool_calls:
                    i = tc.index
                    if i not in tool_calls:
                        tool_calls[i] = {"id": "", "name": "", "args": ""}
                    if tc.id:
                        tool_calls[i]["id"] = tc.id
                    if tc.function.name:
                        tool_calls[i]["name"] += tc.function.name
                    if tc.function.arguments:
                        tool_calls[i]["args"] += tc.function.arguments

        if tool_calls:
            calls = [tool_calls[i] for i in sorted(tool_calls)]
            msg = {
                "role": "assistant",
                "content": full_text or None,
                "tool_calls": [{"id": c["id"], "type": "function",
                                "function": {"name": c["name"], "arguments": c["args"]}}
                               for c in calls],
            }
            self.messages.append({k: v for k, v in msg.items() if v is not None})
            # 返回列表（多工具）或单个 dict（单工具，保持向后兼容）
            actions = [{"name": c["name"], "arguments": c["args"], "id": c["id"]} for c in calls]
            return actions if len(actions) > 1 else actions[0]
        if full_text:
            self.messages.append({"role": "assistant", "content": full_text})
            return {"text": full_text}
        return None

    def _feed_native_result(self, tool_id: str, result: dict, image_path: str | None = None):
        content = json.dumps(result, ensure_ascii=False)
        self.messages.append({"role": "tool", "tool_call_id": tool_id, "content": content})
        if image_path:
            self._append_user("这是截图结果。", image_path)

    # ---- Text fallback mode (no tool calling support) ----
    def _call_text(self) -> dict | None:
        self._compress_context()
        resp = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=self.messages,
        )
        if not resp.choices:
            return None
        text = resp.choices[0].message.content
        self.messages.append({"role": "assistant", "content": text})
        m = re.search(r"```json\s*(\{.*?\})\s*```", text[:8000], re.DOTALL)
        if not m:
            m = re.search(r"(\{[^{}]*\"name\"[^{}]*\})", text)
        if m:
            return json.loads(m.group(1))
        return None

    def _feed_text_result(self, result: dict, image_path: str | None = None):
        text = f"Tool result: {json.dumps(result, ensure_ascii=False)}"
        self._append_user(text, image_path)

    # ---- Main loop ----
    def step(self) -> dict | None:
        """Run one think-act cycle. Returns text reply, tool result, or None."""
        if self.use_native_tools:
            action = self._call_native()
        else:
            action = self._call_text()

        if not action:
            return None

        # Model replied with text, no tool call
        if isinstance(action, dict) and "text" in action and "name" not in action:
            return {"text": action["text"]}

        actions = action if isinstance(action, list) else [action]
        results: list[dict] = []
        for one_action in actions:
            result = execute(one_action)
            image_path = result.get("image")
            feed_result = {k: v for k, v in result.items() if k != "image"}

            # ── ReAct retry hint ──────────────────────────────────────────
            if not result.get("ok", True):
                self._fail_streak += 1
                if self._fail_streak == 1:
                    feed_result["result"] = (
                        feed_result.get("result", "")
                        + "\n\n[系统提示] 此步骤失败，请分析原因并尝试不同方案重试。"
                    )
                elif self._fail_streak == 2:
                    feed_result["result"] = (
                        feed_result.get("result", "")
                        + "\n\n[系统提示] 这是第2次失败，请换一种完全不同的方案，这是最后一次自动重试机会。"
                    )
                else:
                    feed_result["result"] = (
                        feed_result.get("result", "")
                        + "\n\n[系统提示] 已连续失败3次，请停止尝试，向用户说明情况并询问如何继续。"
                    )
                    self._fail_streak = 0
            else:
                self._fail_streak = 0
            # ─────────────────────────────────────────────────────────────

            if self.use_native_tools:
                self._feed_native_result(one_action.get("id", ""), feed_result, image_path)
            else:
                self._feed_text_result(feed_result, image_path)
            results.append(result)

        if len(results) == 1:
            return results[0]

        done_result = next((r for r in results if r.get("done")), None)
        if done_result:
            return done_result

        summary = " | ".join(r.get("result", "") for r in results if r.get("result"))
        merged = {
            "ok": all(r.get("ok", True) for r in results),
            "result": summary,
            "results": results,
        }
        last_image = next((r.get("image") for r in reversed(results) if r.get("image")), None)
        if last_image:
            merged["image"] = last_image
        return merged

    def run(self, task: str, max_steps: int = 30) -> str:
        """Execute a full task with screenshot-analyze-act loop."""
        self._append_user(f"Task: {task}")
        for i in range(max_steps):
            result = self.step()
            if not result:
                break
            log.info("[Step %d] %s", i + 1, result.get("result", ""))
            if result.get("done"):
                return result["result"]
        return "Max steps reached or model stopped."
