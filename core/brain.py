import json
import re
import base64
import logging

from core.adapter import UniversalLLM
from actions.executor import TOOLS_SCHEMA, SCREENSHOT_PATH, execute, _skill_manager
from memory.store import MemoryStore
from config import config

log = logging.getLogger(__name__)

_TOKEN_LIMIT = 30_000
_KEEP_TAIL = 12
_COMPRESS_HEAD = 3
_TOOL_RESULT_MAX = 500

SYSTEM_PROMPT = """你是 Starbot，一个跑在用户电脑上的 AI 私人助手。

## 个性
你是一个严谨且幽默的私人助手。
- 做事靠谱、细致，给出的方案经过思考，不敷衍
- 说话简洁，不废话，不用"好的！""当然！""已为您完成"这种服务员腔
- 适当幽默，让交流轻松自然，但不影响专业判断
- 有自己的判断，不做无脑应声虫；如果用户的方案有问题，直接说

## 运行环境
你同时支持 Discord 和本地桌面端（Web UI）两种客户端。
- 桌面端用户可能通过悬浮输入框发送消息，也可能附带文件（图片、代码文件等）
- 收到文件附件时，图片会以 vision 形式呈现，文本/代码文件内容会拼接在消息中（以 [File: xxx] 标记）
- 根据实际客户端环境灵活应对，不要假设用户一定在用哪个端

## 用户偏好感知
每次对话都要留意用户流露出的偏好和习惯，例如：
- 用哪种语言/框架/工具、喜欢什么风格的代码
- 常用哪些软件，桌面布局习惯
- 沟通风格：喜欢详细解释还是直接给结论
- 重复出现的需求/任务类型

发现有价值的偏好 → 立刻 memory_save(category="preference", importance=8)

## ★ 任务执行协议（必须遵守）

### 1. 规划 — 复杂任务先分解
凡是涉及 2 步以上操作的任务，**必须先输出编号计划，再开始执行**：
> 好，分三步：① 先查X ② 再做Y ③ 最后验证Z，开始执行……

简单对话/单步操作不需要计划，直接做。

### 2. 迭代 — 失败换方案，不接受烂结果
- 工具调用失败 → 分析原因，换方案重试，**最多尝试 3 种不同方法**
- 结果质量不满足需求 → 调整参数或换工具，不提交低质量结果
- 禁止连续调同一个失败工具超过 2 次，必须先换思路

### 3. 复盘 — 完成后回顾（仅多步任务）
多步任务全部完成后，一句话说清楚做了什么、遇到什么坑。
有价值的经验立刻 memory_save（knowledge/experience）。

## 判断逻辑
- 闲聊/问答 → 直接回复，不调用工具
- 需要查资料 → web_search → fetch_page 读原文
- 需要操作电脑 → 调用工具执行

## ★ Skills 优先原则
你有一套可扩展的技能（skills）系统，用户可以安装各种技能插件。
- 接到任务时，**优先检查已安装的 skills 是否能完成**，有对应 skill 就直接用
- 不要在有现成 skill 的情况下自己手动拼凑方案
- 系统会在首条消息中附带 [Skill Recommendations]，务必参考

## 屏幕操作（仅限用户要求时使用）
截图（screenshot）、模拟键盘输入（keyboard_*）、鼠标操作（mouse_*）等屏幕交互类工具，**只在用户明确要求时才使用**。
- 用户说"帮我点""帮我操作""看看屏幕上""截个图"等 → 可以使用
- 用户没提到屏幕操作 → **不要主动截图或模拟输入**，用文件/命令行等非侵入方式完成任务
- 截图上有红色坐标网格（每200px一条线），用网格精确定位坐标
- 看不清细节：screenshot_region 放大，或 read_screen_text OCR
- 找不到按钮位置：find_image 用模板图匹配，比坐标更可靠
- 需要操作特定窗口：先 window_focus 切换，再操作

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
- 任务有价值的经验完成后 memory_save

## 学习策略
上网：web_search → fetch_page 读原文 → 多源交叉验证 → memory_save 结构化笔记
视频：learn_video_plus 学习视频（支持 YouTube/B站等 1000+ 平台，自动字幕+Whisper转写）
保存记忆时：写清楚来源、核心要点、适用场景

## 多任务
耗时任务用 bg_task 放后台，完成后用 notify 提醒用户。用 task_status 查进度。

## ★ 记忆管理规则（严格执行）

### 保存门槛 — 只有以下情况才 memory_save：
1. **用户明确要求**记住某件事（"记住""下次记得"等措辞）
2. **用户偏好/习惯**：语言风格、工具选择、工作流偏好等，importance=8
3. **真正可复用的经验**：踩坑记录、特定环境下的操作要点，importance=7
4. **用户主动要求学习**的知识/资料
5. **长期项目信息**：项目结构、关键路径、重要约定

### 禁止保存：
- 临时任务的执行结果（"帮我搜了XX""打开了XX文件"）
- 已完成/已修复的功能开发进度（"实现了XX功能""修复了XX bug"）
- 一次性指令或当次会话的上下文
- 可以随时重新获取的普通信息（天气、新闻、临时查询结果）

### 主动清理 — 以下情况主动调用 memory_delete：
- 用户说"不用记了""删掉""清一下记忆"→ 立刻执行
- 发现记忆里有已完成的 todo、已修复的 bug、已实现的功能 → 删除
- 记忆内容与当前已知事实明显矛盾/过时 → 删除旧的，保存新的
- 用户要求清空全部 → memory_delete(mode="clear_all")

### 检索策略：
- memory_recall：用 **2-5 个核心关键词**，搜不到就换同义词
- 首次对话先检索相关偏好，有偏好直接采用

## 格式
- 纯文字问答：直接回复，末尾加 ✦，**不调用任何工具（包括 done）**
- 多步操作任务全部完成后才调用 done（result 填一句话结论）
- **严禁**输出纯数字序列（如 1\\n2\\n3\\n...），规划步骤必须用 ①②③ 或 "1. 描述" 格式"""

TEXT_MODE_SUFFIX = """

Since tool calling is not available, respond with a JSON block to invoke a tool:
```json
{"name": "tool_name", "arguments": {...}}
```
Output ONLY the JSON block, no other text."""


class Brain:
    # Tools that require user confirmation before execution
    DANGEROUS_TOOLS = frozenset({
        "power", "process_kill", "file_delete", "registry_write",
        "registry_delete_value", "run_command",
    })

    def __init__(self, llm: UniversalLLM | None = None, use_native_tools: bool = True, tools_schema: list | None = None,
                 confirm_callback=None):
        self.llm = llm or UniversalLLM(
            config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL,
        )
        self.use_native_tools = use_native_tools
        self._tools_schema = tools_schema if tools_schema is not None else TOOLS_SCHEMA
        self._confirm_callback = confirm_callback
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

    def _append_user(self, text: str, image_path: str | None = None, attachments: list[dict] | None = None):
        # 首条用户消息只注入 Skill 推荐，不再自动拼接 [Relevant Memory] 文本，避免“系统自动加记忆”干扰对话。
        if len(self.messages) == 1 and text and not image_path:
            try:
                rec_hint = _skill_manager.build_recommendation_hint(text, limit=3)
            except Exception as e:
                log.debug("skill recommendation hint failed: %s", e)
                rec_hint = ""
            if rec_hint:
                # 仅作为隐藏提示放在同一条 user 消息的前缀，供模型参考，不建议在回答中直接复述标签。
                text = f"[Skill Recommendations]\n{rec_hint}\n\n{text}"

        # Process web UI attachments
        content_parts: list[dict] = []
        if attachments:
            for att in attachments:
                att_type = att.get("type", "")
                att_name = att.get("name", "file")
                att_data = att.get("data_b64", "")
                if att_type.startswith("image/") and att_data:
                    # Image attachment → vision content part
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{att_type};base64,{att_data}"},
                    })
                elif att_data:
                    # Text/code file → decode and prepend to message text
                    try:
                        file_text = base64.b64decode(att_data).decode("utf-8", errors="replace")
                    except Exception:
                        file_text = "(unable to decode file)"
                    text = f"[File: {att_name}]\n{file_text}\n\n{text}"

        if image_path:
            img = self._image_content(image_path)
            if img:
                content_parts.append(img)

        if content_parts:
            content_parts.insert(0, {"type": "text", "text": text})
            self.messages.append({"role": "user", "content": content_parts})
            return
        self.messages.append({"role": "user", "content": text})

    # ---- Vision fallback helpers ----
    def _strip_images(self, messages: list[dict]) -> list[dict]:
        """Return a copy of messages with all image_url parts removed (text only)."""
        out = []
        for msg in messages:
            c = msg.get("content")
            if isinstance(c, list):
                text_parts = [p for p in c if isinstance(p, dict) and p.get("type") == "text"]
                text = " ".join(p.get("text", "") for p in text_parts) or "[image]"
                out.append({**msg, "content": text})
            else:
                out.append(msg)
        return out

    def _has_images(self) -> bool:
        for msg in self.messages:
            c = msg.get("content")
            if isinstance(c, list):
                for p in c:
                    if isinstance(p, dict) and p.get("type") == "image_url":
                        return True
        return False

    # ---- Native tool calling mode ----
    def _call_native(self) -> dict | list | None:
        self._compress_context()
        try:
            resp = self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=self.messages,
                tools=self._tools_schema,
            )
        except Exception as e:
            # If the model doesn't support images, retry without them
            if self._has_images() and ("image" in str(e).lower() or "vision" in str(e).lower() or "404" in str(e)):
                log.warning("Model does not support images, retrying without: %s", e)
                stripped = self._strip_images(self.messages)
                resp = self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=stripped,
                    tools=self._tools_schema,
                )
            else:
                raise
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

    def _call_native_stream(self, on_chunk=None, on_clear=None, cancel_check=None) -> dict | None:
        """Stream version of _call_native. Calls on_chunk(text) with each text delta.
        Calls on_clear() once when tool calls are first detected (LLM switched from
        text to tool-call mode — previously streamed text was just internal planning).
        cancel_check: callable returning True if cancellation was requested.
        Returns list of tool calls or single text action."""
        self._compress_context()
        try:
            stream = self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=self.messages,
                tools=self._tools_schema,
                stream=True,
            )
        except Exception as e:
            if self._has_images() and ("image" in str(e).lower() or "vision" in str(e).lower() or "404" in str(e)):
                log.warning("Model does not support images (stream), retrying without: %s", e)
                stripped = self._strip_images(self.messages)
                stream = self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=stripped,
                    tools=self._tools_schema,
                    stream=True,
                )
            else:
                raise
        full_text = ""
        tool_calls: dict[int, dict] = {}
        _tool_call_signalled = False   # 只触发一次 on_clear

        for chunk in stream:
            if cancel_check and cancel_check():
                # Abort streaming — close the stream and return None
                try:
                    stream.close()
                except Exception:
                    pass
                return None
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
        return self._process_action(action)

    def step_stream(self, on_chunk=None, on_clear=None, cancel_check=None) -> dict | None:
        """Stream version of step. Calls on_chunk(text) for each text delta.
        cancel_check: callable returning True if cancellation was requested."""
        if self.use_native_tools:
            action = self._call_native_stream(on_chunk=on_chunk, on_clear=on_clear, cancel_check=cancel_check)
        else:
            action = self._call_text()
        return self._process_action(action, streamed=True)

    def _process_action(self, action, streamed=False) -> dict | None:

        if not action:
            return None

        # Model replied with text, no tool call
        if isinstance(action, dict) and "text" in action and "name" not in action:
            result = {"text": action["text"]}
            if streamed:
                result["streamed"] = True
            return result

        actions = action if isinstance(action, list) else [action]
        results: list[dict] = []
        for one_action in actions:
            tool_name = one_action.get("name", "")

            # ── Confirmation gate for dangerous tools ─────────────────────
            if tool_name in self.DANGEROUS_TOOLS and self._confirm_callback:
                try:
                    args_str = one_action.get("arguments", "{}")
                    if isinstance(args_str, str):
                        display_args = json.loads(args_str)
                    else:
                        display_args = args_str
                except Exception:
                    display_args = one_action.get("arguments", {})
                approved = self._confirm_callback(tool_name, display_args)
                if not approved:
                    denied_result = {"ok": False, "result": f"用户拒绝执行 {tool_name}"}
                    if self.use_native_tools:
                        self._feed_native_result(one_action.get("id", ""), denied_result, None)
                    else:
                        self._feed_text_result(denied_result, None)
                    results.append(denied_result)
                    continue
            # ──────────────────────────────────────────────────────────────

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
