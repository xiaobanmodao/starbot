import sys
import os
import time
import asyncio
import json
import logging
import psutil
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

import re
import discord
import pyautogui

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config, _save_state
from actions.executor import SCREENSHOT_PATH, _task_mgr, execute, _skill_manager, get_tools_schema
import actions.executor as _executor
from core.adapter import UniversalLLM
from core.brain import Brain
from memory.store import MemoryStore
from core.op_log import undo_last

intents = discord.Intents.default()
intents.message_content = True
_SESSION_DIR = Path(__file__).resolve().parent.parent / "logs" / "sessions"

# 执行前需要用户确认的危险工具
_CONFIRM_TOOLS: set = {
    "file_delete",
    "power",
    "process_kill",
    "registry_write",
    "registry_delete_value",
}


# ── Discord UI Views ───────────────────────────────────────────────────────────

class ConfirmView(discord.ui.View):
    """Two-button confirmation: ✅ confirm / ❌ cancel. Auto-times-out at `timeout` seconds."""

    def __init__(self, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.value: bool | None = None

    @discord.ui.button(label="✅ 确认", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, _btn):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, _btn):
        self.value = False
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        self.value = None   # signals caller to treat as cancel


class StarBotClient(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_tasks: dict[int, str] = {}
        self._active_task_handles: dict[int, asyncio.Task] = {}
        self._active_session_handles: dict[int, asyncio.Task] = {}
        self._session_brains: dict[int, Brain] = {}
        self._model_list = {}
        self._pending_confirm: dict[int, asyncio.Future] = {}
        self._notify_channel = None
        self._llm = UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)
        self.tree = discord.app_commands.CommandTree(self)
        self._register_slash_commands()

    def _is_owner_interaction(self, interaction: discord.Interaction) -> bool:
        oid = config.DISCORD_OWNER_ID
        return str(interaction.user.id) == oid or str(interaction.user.name) == oid

    def _register_slash_commands(self):
        """注册所有 Discord 斜杠命令（在 on_ready 中 sync）。"""

        # ── /help ──────────────────────────────────────────────────────────
        @self.tree.command(name="help", description="显示 Starbot 所有可用命令")
        async def slash_help(interaction: discord.Interaction):
            if not self._is_owner_interaction(interaction):
                return
            embed = discord.Embed(title="📖 Starbot 命令", color=0x3498db)
            embed.add_field(name="对话", value="直接在频道发消息即可", inline=False)
            embed.add_field(name="/status", value="查看系统状态和后台任务", inline=False)
            embed.add_field(name="/stop", value="停止当前任务", inline=False)
            embed.add_field(name="/screenshot", value="截取当前屏幕", inline=False)
            embed.add_field(name="/model [名称]", value="查看/切换模型", inline=False)
            embed.add_field(name="/skill [list|install|remove|reload]", value="管理 skill 插件", inline=False)
            embed.add_field(name="/memory [list|search|delete|stats]", value="管理 AI 记忆", inline=False)
            embed.add_field(name="/reset", value="清空当前频道会话上下文", inline=False)
            embed.add_field(name="/usage", value="查看本会话 token 用量", inline=False)
            embed.add_field(name="/tasks", value="查看后台任务列表", inline=False)
            embed.add_field(name="/config [key] [value]", value="查看/修改配置项", inline=False)
            embed.add_field(name="/rollback [n]", value="撤销最近 n 次文件操作（默认 1）", inline=False)
            await interaction.response.send_message(embed=embed)

        # ── /status ────────────────────────────────────────────────────────
        @self.tree.command(name="status", description="查看系统状态和后台任务")
        async def slash_status(interaction: discord.Interaction):
            if not self._is_owner_interaction(interaction):
                return
            await interaction.response.defer()
            t0 = time.time()
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            task_str = "\n".join(f"• {d}" for d in self._active_tasks.values()) or "空闲"
            embed = discord.Embed(title="📊 系统状态", color=0x3498db, timestamp=datetime.now())
            embed.add_field(name="CPU", value=f"{cpu}%", inline=True)
            embed.add_field(name="内存", value=f"{mem.percent}% ({mem.used//(1024**3)}/{mem.total//(1024**3)} GB)", inline=True)
            embed.add_field(name="当前对话", value=task_str, inline=False)
            embed.add_field(name="后台任务", value=_task_mgr.summary(), inline=False)
            embed.set_footer(text=self._footer(t0))
            await interaction.followup.send(embed=embed)

        # ── /stop ──────────────────────────────────────────────────────────
        @self.tree.command(name="stop", description="停止当前正在执行的任务")
        async def slash_stop(interaction: discord.Interaction):
            if not self._is_owner_interaction(interaction):
                return
            tasks = set(self._active_task_handles.values()) | set(self._active_session_handles.values())
            if not tasks:
                await interaction.response.send_message("当前没有正在执行的任务", ephemeral=True)
                return
            count = len(tasks)
            for t in tasks:
                t.cancel()
            self._active_task_handles.clear()
            self._active_session_handles.clear()
            self._active_tasks.clear()
            await interaction.response.send_message(f"✋ 已停止 {count} 个任务")

        # ── /screenshot ────────────────────────────────────────────────────
        @self.tree.command(name="screenshot", description="截取当前屏幕")
        async def slash_screenshot(interaction: discord.Interaction):
            if not self._is_owner_interaction(interaction):
                return
            await interaction.response.defer()
            import io
            from PIL import Image
            t0 = time.time()
            img = pyautogui.screenshot()
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=75)
            buf.seek(0)
            embed = discord.Embed(title="🖥️ 当前屏幕截图", color=0x2ecc71, timestamp=datetime.now())
            embed.set_image(url="attachment://screen.jpg")
            embed.set_footer(text=self._footer(t0))
            await interaction.followup.send(embed=embed, file=discord.File(buf, filename="screen.jpg"))

        # ── /model ─────────────────────────────────────────────────────────
        @self.tree.command(name="model", description="查看或切换 LLM 模型")
        @discord.app_commands.describe(name="要切换到的模型名称（不填则列出所有可用模型）")
        async def slash_model(interaction: discord.Interaction, name: str = None):
            if not self._is_owner_interaction(interaction):
                return
            t0 = time.time()
            if name:
                config.LLM_MODEL = name
                self._llm.model = name
                _save_state({"LLM_MODEL": name})
                embed = discord.Embed(title="模型已切换", description=f"`{name}`", color=0x2ecc71)
                embed.set_footer(text=self._footer(t0))
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.defer()
                try:
                    resp = await asyncio.to_thread(
                        lambda: self._llm.client.with_options(timeout=8).models.list()
                    )
                    models = [m.id for m in resp.data]
                    names = "\n".join(f"`{i+1}.` {m}" for i, m in enumerate(models))
                    if len(names) > 3900:
                        names = names[:3900] + "\n..."
                    embed = discord.Embed(title="可用模型", description=names, color=0x3498db)
                    embed.add_field(name="当前模型", value=f"`{config.LLM_MODEL}`")
                    embed.set_footer(text="使用 /model <name> 切换")
                    await interaction.followup.send(embed=embed)
                except Exception as e:
                    await interaction.followup.send(f"获取模型列表失败：{e}")

        # ── /reset ─────────────────────────────────────────────────────────
        @self.tree.command(name="reset", description="清空当前频道的会话上下文")
        async def slash_reset(interaction: discord.Interaction):
            if not self._is_owner_interaction(interaction):
                return
            t0 = time.time()
            session_key = interaction.channel_id
            self._session_brains.pop(session_key, None)
            f = self._session_file(session_key)
            try:
                if f.exists():
                    f.unlink()
            except Exception:
                pass
            embed = discord.Embed(description="✅ 当前频道会话已重置，上下文已清空", color=0x2ecc71)
            embed.set_footer(text=self._footer(t0))
            await interaction.response.send_message(embed=embed)

        # ── /usage ─────────────────────────────────────────────────────────
        @self.tree.command(name="usage", description="查看本频道会话的 token 用量")
        async def slash_usage(interaction: discord.Interaction):
            if not self._is_owner_interaction(interaction):
                return
            t0 = time.time()
            brain = self._session_brains.get(interaction.channel_id)
            if brain is None:
                embed = discord.Embed(description="当前没有活跃会话，无 token 统计", color=0x95a5a6)
            else:
                u = brain.usage
                embed = discord.Embed(
                    title="📊 Token 用量（本会话）",
                    description=(
                        f"**输入 tokens:** {u.get('input',0):,}\n"
                        f"**输出 tokens:** {u.get('output',0):,}\n"
                        f"**API 调用次数:** {u.get('calls',0)}"
                    ),
                    color=0x3498db,
                )
            embed.set_footer(text=self._footer(t0))
            await interaction.response.send_message(embed=embed)

        # ── /tasks ─────────────────────────────────────────────────────────
        @self.tree.command(name="tasks", description="查看后台任务列表")
        async def slash_tasks(interaction: discord.Interaction):
            if not self._is_owner_interaction(interaction):
                return
            t0 = time.time()
            embed = discord.Embed(
                title="📋 后台任务",
                description=_task_mgr.summary() or "暂无后台任务",
                color=0x3498db,
            )
            embed.set_footer(text=self._footer(t0))
            await interaction.response.send_message(embed=embed)

        # ── /rollback ──────────────────────────────────────────────────────
        @self.tree.command(name="rollback", description="撤销最近 N 次文件写入/删除操作")
        @discord.app_commands.describe(n="撤销次数（默认 1，最多 10）")
        async def slash_rollback(interaction: discord.Interaction, n: int = 1):
            if not self._is_owner_interaction(interaction):
                return
            n = max(1, min(10, n))
            await interaction.response.defer()
            t0 = time.time()
            msgs = await asyncio.to_thread(undo_last, n)
            result = "\n".join(msgs)
            color = 0x2ecc71 if any("✅" in m for m in msgs) else 0xe74c3c
            embed = discord.Embed(title="⏪ 撤销结果", description=result[:4000], color=color)
            embed.set_footer(text=self._footer(t0))
            await interaction.followup.send(embed=embed)

        # ── /memory ────────────────────────────────────────────────────────
        @self.tree.command(name="memory", description="管理 AI 记忆 (子命令: list/search/delete/stats)")
        @discord.app_commands.describe(
            subcommand="子命令：list / search / delete / stats",
            arg="search 的关键词 或 delete 的 ID",
        )
        async def slash_memory(interaction: discord.Interaction, subcommand: str = "list", arg: str = ""):
            if not self._is_owner_interaction(interaction):
                return
            t0 = time.time()
            # Reuse existing handler by faking the text
            fake_text = f"/memory {subcommand} {arg}".strip()

            class _FakeMsg:
                content = fake_text
                author = interaction.user
                channel = interaction.channel

            await interaction.response.defer()
            mem = MemoryStore()
            sub = subcommand.lower()

            if sub == "stats":
                stats = mem.stats()
                lines = "\n".join(f"**{cat}**: {cnt}" for cat, cnt in stats.items()) or "暂无记忆"
                embed = discord.Embed(title="🧠 记忆统计", description=lines, color=0x3498db)
                embed.set_footer(text=f"共 {sum(stats.values())} 条 | {self._footer(t0)}")
            elif sub == "search":
                if not arg:
                    await interaction.followup.send("用法：`/memory search <关键词>`")
                    return
                results = mem.search_multi(arg, limit=8)
                if not results:
                    embed = discord.Embed(description=f"未找到包含 `{arg}` 的记忆", color=0xe74c3c)
                else:
                    lines = [f"`#{r['id']}` [{r['category']}] {r['content'][:120].replace(chr(10),' ')}" for r in results]
                    embed = discord.Embed(title=f"🔍 搜索：{arg}", description="\n".join(lines), color=0x3498db)
                embed.set_footer(text=self._footer(t0))
            elif sub == "delete":
                if not arg or not arg.isdigit():
                    await interaction.followup.send("用法：`/memory delete <ID>`")
                    return
                ok = mem.delete_by_id(int(arg))
                embed = discord.Embed(
                    description=f"{'✅ 已删除' if ok else '❌ 删除失败'} ID={arg}",
                    color=0x2ecc71 if ok else 0xe74c3c,
                )
                embed.set_footer(text=self._footer(t0))
            else:
                category = "" if sub == "list" else sub
                rows = mem.list_by_category(category, limit=15)
                if not rows:
                    embed = discord.Embed(description="暂无记忆" + (f" (分类: {category})" if category else ""), color=0x95a5a6)
                else:
                    lines = [f"`#{r['id']}` [{r['category']}] ★{r['importance']} {r['content'][:100].replace(chr(10),' ')}" for r in rows]
                    embed = discord.Embed(title="🧠 记忆列表" + (f" — {category}" if category else ""), description="\n".join(lines), color=0x3498db)
                embed.set_footer(text=f"/memory search <词>  |  /memory delete <ID>  |  /memory stats | {self._footer(t0)}")

            await interaction.followup.send(embed=embed)

        # ── /skill ─────────────────────────────────────────────────────────
        @self.tree.command(name="skill", description="管理 Skill 插件 (子命令: list/install/remove/reload)")
        @discord.app_commands.describe(
            subcommand="子命令：list / install / remove / reload",
            arg="install 的 URL/路径，或 remove 的 skill 名称",
        )
        async def slash_skill(interaction: discord.Interaction, subcommand: str = "list", arg: str = ""):
            if not self._is_owner_interaction(interaction):
                return
            sub = subcommand.lower()
            if sub == "list":
                skills = _skill_manager.list_skills()
                if not skills:
                    embed = discord.Embed(title="🔌 已安装的 Skills", description="暂无已安装的 skill", color=0x3498db)
                else:
                    embed = discord.Embed(title="🔌 已安装的 Skills", color=0x3498db)
                    for s in skills:
                        tools_str = "、".join(f"`{t}`" for t in s["tools"]) or "（无工具）"
                        embed.add_field(name=f"{s['name']} v{s['version']}", value=f"{s['description']}\n工具：{tools_str}", inline=False)
                await interaction.response.send_message(embed=embed)
            elif sub == "install":
                if not arg:
                    await interaction.response.send_message("用法：`/skill install <URL 或路径>`", ephemeral=True)
                    return
                await interaction.response.defer()
                ok, msg = await asyncio.to_thread(_skill_manager.install, arg)
                embed = discord.Embed(description=f"{'✅' if ok else '❌'} {msg}", color=0x2ecc71 if ok else 0xe74c3c)
                await interaction.followup.send(embed=embed)
            elif sub == "remove":
                if not arg:
                    await interaction.response.send_message("用法：`/skill remove <skill名称>`", ephemeral=True)
                    return
                ok, msg = _skill_manager.remove(arg)
                embed = discord.Embed(description=f"{'✅' if ok else '❌'} {msg}", color=0x2ecc71 if ok else 0xe74c3c)
                await interaction.response.send_message(embed=embed)
            elif sub == "reload":
                _skill_manager.reload()
                skills = _skill_manager.list_skills()
                embed = discord.Embed(description=f"✅ 已重新加载，共 {len(skills)} 个 skill", color=0x2ecc71)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("未知子命令，可用：list / install / remove / reload", ephemeral=True)

        # ── /config ────────────────────────────────────────────────────────
        @self.tree.command(name="config", description="查看或修改配置项")
        @discord.app_commands.describe(key="配置键（如 LLM_MODEL）", value="新值（不填则仅查看）")
        async def slash_config(interaction: discord.Interaction, key: str = None, value: str = None):
            if not self._is_owner_interaction(interaction):
                return
            t0 = time.time()
            EDITABLE = {"LLM_MODEL", "LLM_API_BASE", "LLM_API_KEY", "DISCORD_PROXY"}
            if key is None:
                lines = [f"`{k}`: `{getattr(config, k, '')}`" for k in sorted(EDITABLE)]
                embed = discord.Embed(title="⚙️ 配置项", description="\n".join(lines), color=0x3498db)
                embed.set_footer(text="/config <key> <value> 修改 | " + self._footer(t0))
            elif value is None:
                k = key.upper()
                val = getattr(config, k, "（未知配置项）")
                embed = discord.Embed(description=f"`{k}` = `{val}`", color=0x3498db)
                embed.set_footer(text=self._footer(t0))
            else:
                k = key.upper()
                if k not in EDITABLE:
                    await interaction.response.send_message(f"❌ 不允许修改 `{k}`", ephemeral=True)
                    return
                setattr(config, k, value)
                if k in ("LLM_MODEL", "LLM_API_BASE", "LLM_API_KEY"):
                    self._llm = UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)
                _save_state({k: value})
                embed = discord.Embed(description=f"✅ `{k}` 已更新为 `{value}`", color=0x2ecc71)
                embed.set_footer(text=self._footer(t0))
            await interaction.response.send_message(embed=embed)

    def _footer(self, t0: float) -> str:
        ms = int((time.time() - t0) * 1000)
        return f"{config.LLM_API_BASE} / {config.LLM_MODEL} | {ms}ms"

    def _is_owner(self, message: discord.Message) -> bool:
        oid = config.DISCORD_OWNER_ID
        return str(message.author.id) == oid or str(message.author.name) == oid

    def _session_key(self, message: discord.Message) -> int:
        # 每个频道（含 Thread）用自己的 channel.id 作为会话键，
        # 同一频道内的对话持续保持上下文。
        return message.channel.id

    def _session_file(self, session_key: int) -> Path:
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        return _SESSION_DIR / f"{session_key}.json"

    @staticmethod
    def _normalize_content(content):
        if isinstance(content, str) or content is None:
            return content
        if isinstance(content, list):
            text_parts = []
            has_image = False
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    t = part.get("text", "")
                    if t:
                        text_parts.append(t)
                elif ptype == "image_url":
                    has_image = True
            if text_parts:
                return "\n".join(text_parts)
            return "[image omitted]" if has_image else ""
        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False)[:4000]
        return str(content)

    def _serialize_messages(self, messages: list[dict]) -> list[dict]:
        out: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            if role not in {"system", "user", "assistant", "tool"}:
                continue
            item = {"role": role}

            if "tool_call_id" in msg and isinstance(msg.get("tool_call_id"), str):
                item["tool_call_id"] = msg["tool_call_id"]
            if "tool_calls" in msg and isinstance(msg.get("tool_calls"), list):
                tool_calls = []
                for tc in msg["tool_calls"]:
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
                    tool_calls.append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": fn.get("arguments", "{}"),
                        },
                    })
                if tool_calls:
                    item["tool_calls"] = tool_calls

            content = self._normalize_content(msg.get("content"))
            if content is not None:
                item["content"] = content
            out.append(item)

        # Keep recent history to avoid unbounded file growth.
        if len(out) > 200:
            head = [m for m in out[:1] if m.get("role") == "system"]
            tail = out[-199:]
            out = head + [m for m in tail if m.get("role") != "system"]
        return out

    def _persist_session(self, session_key: int, brain: Brain):
        try:
            file = self._session_file(session_key)
            data = {
                "version": 1,
                "updated_at": int(time.time()),
                "messages": self._serialize_messages(brain.messages),
            }
            tmp = file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(file)
        except Exception as e:
            log.warning("Failed to persist session %s: %s", session_key, e)

    def _load_persisted_session(self, session_key: int) -> Brain | None:
        file = self._session_file(session_key)
        if not file.exists():
            return None
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            msgs = data.get("messages")
            if not isinstance(msgs, list) or not msgs:
                return None
            brain = Brain(llm=self._llm, tools_schema=get_tools_schema())
            restored = [brain.messages[0]]
            for msg in msgs:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                if role == "system":
                    continue
                if role not in {"user", "assistant", "tool"}:
                    continue
                item = {"role": role}
                if "content" in msg:
                    item["content"] = self._normalize_content(msg.get("content"))
                if role == "assistant" and isinstance(msg.get("tool_calls"), list):
                    item["tool_calls"] = msg["tool_calls"]
                if role == "tool" and isinstance(msg.get("tool_call_id"), str):
                    item["tool_call_id"] = msg["tool_call_id"]
                restored.append(item)
            brain.messages = restored
            return brain
        except Exception as e:
            log.warning("Failed to load session %s: %s", session_key, e)
            return None

    async def on_ready(self):
        log.info("Discord Connected: %s (guilds: %s)", self.user, len(self.guilds))
        # 同步斜杠命令到所有服务器（guild sync 立即生效，global sync 最多 1 小时）
        for guild in self.guilds:
            try:
                await self.tree.sync(guild=guild)
                log.info("Slash commands synced to guild: %s", guild.name)
            except Exception as e:
                log.warning("Failed to sync commands to guild %s: %s", guild.name, e)

        # 优先用配置的通知频道，否则取第一个可写文字频道
        ch = None
        if config.DISCORD_CHANNEL_ID:
            ch = self.get_channel(config.DISCORD_CHANNEL_ID)
        if ch is None:
            for guild in self.guilds:
                for channel in guild.text_channels:
                    ch = channel
                    break
                if ch:
                    break

        if ch:
            self._notify_channel = ch
            loop = asyncio.get_event_loop()
            def _bg_done(info):
                icon = "✅" if info.status == "done" else "❌"
                snippet = info.result[:200] if info.result else ""
                embed = discord.Embed(
                    title=f"{icon} 后台任务完成：{info.name}",
                    description=snippet,
                    color=0x2ecc71 if info.status == "done" else 0xe74c3c,
                )
                asyncio.run_coroutine_threadsafe(ch.send(embed=embed), loop)
            _executor._on_bg_task_done = _bg_done
            # 注册全局 notifier，供后台监控 skill 使用
            from core import notifier as _notifier
            _notifier.setup(loop, ch)
            embed = discord.Embed(title="✦ Starbot 已就绪", color=0x5865f2, timestamp=datetime.now())
            embed.add_field(name="覆盖范围", value="服务器所有文字频道", inline=True)
            embed.add_field(name="会话模式", value="每个频道独立持久化上下文", inline=True)
            embed.set_footer(text=f"{config.LLM_API_BASE} / {config.LLM_MODEL}")
            await ch.send(embed=embed)

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """新频道创建时自动发送欢迎提示。"""
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            return
        try:
            embed = discord.Embed(
                title="✦ Starbot 已成功加入频道",
                description=(
                    "直接发消息即可开始对话，我会记住这个频道里的所有上下文。\n"
                    "发送 `/help` 查看所有可用命令。"
                ),
                color=0x5865f2,
                timestamp=datetime.now(),
            )
            embed.set_footer(text=f"{config.LLM_API_BASE} / {config.LLM_MODEL}")
            await channel.send(embed=embed)
        except Exception as e:
            log.warning("on_guild_channel_create: 无法发送欢迎消息到 %s: %s", channel.name, e)

    async def on_message(self, message: discord.Message):
        if message.author.bot or not self._is_owner(message):
            return
        # 跳过语音频道（VoiceChannel / StageChannel）
        if isinstance(message.channel, (discord.VoiceChannel, discord.StageChannel)):
            return
        text = message.content.strip()
        if not text:
            return

        t0 = time.time()
        uid = message.author.id
        session_key = self._session_key(message)

        if uid in self._model_list and text.isdigit():
            idx = int(text) - 1
            models = self._model_list.pop(uid)
            if 0 <= idx < len(models):
                config.LLM_MODEL = models[idx]
                self._llm.model = models[idx]
                _save_state({"LLM_MODEL": models[idx]})
                embed = discord.Embed(title="模型已切换", description=f"`{models[idx]}`", color=0x2ecc71)
                embed.set_footer(text=self._footer(t0))
                await message.reply(embed=embed)
            else:
                await message.reply("序号无效，已取消")
            return

        if text == "/status":
            await self._cmd_status(message, t0)
        elif text == "/help":
            await self._cmd_help(message)
        elif text == "/stop":
            await self._cmd_stop(message)
        elif text == "/screenshot":
            await self._cmd_screenshot(message, t0)
        elif text == "/model":
            await self._cmd_model(message, t0)
        elif text.startswith("/model "):
            name = text[7:].strip()
            config.LLM_MODEL = name
            self._llm.model = name
            _save_state({"LLM_MODEL": name})
            embed = discord.Embed(title="模型已切换", description=f"`{name}`", color=0x2ecc71)
            embed.set_footer(text=self._footer(t0))
            await message.reply(embed=embed)
        elif text == "/skill" or text == "/skill list":
            await self._cmd_skill_list(message)
        elif text.startswith("/skill install "):
            await self._cmd_skill_install(message, text[15:].strip())
        elif text.startswith("/skill remove "):
            await self._cmd_skill_remove(message, text[14:].strip())
        elif text == "/skill reload":
            await self._cmd_skill_reload(message)
        elif text == "/memory" or text.startswith("/memory "):
            await self._cmd_memory(message, text, t0)
        elif text == "/reset":
            await self._cmd_reset(message, session_key, t0)
        elif text == "/usage":
            brain = self._session_brains.get(session_key)
            await self._cmd_usage(message, brain, t0)
        elif text == "/tasks":
            await self._cmd_tasks(message, t0)
        elif text.startswith("/config"):
            await self._cmd_config(message, text, t0)
        elif text == "/rollback" or text.startswith("/rollback "):
            await self._cmd_rollback(message, text, t0)
        else:
            self._model_list.pop(uid, None)
            running = self._active_session_handles.get(session_key)
            if running and not running.done():
                await message.reply("上一条消息还在处理中，请稍等，或发送 `/stop` 中断。")
                return
            # 所有频道统一：按 channel.id 恢复或新建持久化会话
            brain = self._session_brains.get(session_key)
            if brain is None:
                brain = self._load_persisted_session(session_key) or Brain(llm=self._llm, tools_schema=get_tools_schema())
                self._session_brains[session_key] = brain
            else:
                brain.llm = self._llm
            brain._append_user(text)

            task = asyncio.create_task(self._handle(message, t0, brain, session_key))
            self._active_task_handles[message.id] = task
            self._active_session_handles[session_key] = task



    async def _cmd_help(self, message: discord.Message):
        embed = discord.Embed(title="📖 Starbot 命令", color=0x3498db)
        embed.add_field(name="对话", value="直接发消息即可", inline=False)
        embed.add_field(name="/status", value="查看系统状态和后台任务", inline=False)
        embed.add_field(name="/stop", value="停止当前任务", inline=False)
        embed.add_field(name="/screenshot", value="截取当前屏幕", inline=False)
        embed.add_field(name="/model [名称]", value="查看/切换模型", inline=False)
        embed.add_field(name="/skill", value="查看/安装/删除 skill 插件", inline=False)
        embed.add_field(name="/memory [list|search|delete|stats]", value="管理 AI 记忆", inline=False)
        embed.add_field(name="/reset", value="清空当前会话上下文", inline=False)
        embed.add_field(name="/usage", value="查看本会话 token 用量", inline=False)
        embed.add_field(name="/tasks", value="查看后台任务列表", inline=False)
        embed.add_field(name="/config [key] [value]", value="查看/修改配置项", inline=False)
        embed.add_field(name="/rollback [n]", value="撤销最近 n 次文件操作（默认 1）", inline=False)
        embed.add_field(name="/help", value="显示此帮助", inline=False)
        await message.reply(embed=embed)

    async def _cmd_status(self, message: discord.Message, t0: float):
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        task_str = "\n".join(f"• {d}" for d in self._active_tasks.values()) or "空闲"
        bg_summary = _task_mgr.summary()
        embed = discord.Embed(title="📊 系统状态", color=0x3498db, timestamp=datetime.now())
        embed.add_field(name="CPU", value=f"{cpu}%", inline=True)
        embed.add_field(name="内存", value=f"{mem.percent}% ({mem.used // (1024**3)}/{mem.total // (1024**3)} GB)", inline=True)
        embed.add_field(name="当前对话", value=task_str, inline=False)
        embed.add_field(name="后台任务", value=bg_summary, inline=False)
        embed.set_footer(text=self._footer(t0))
        await message.reply(embed=embed)

    async def _cmd_screenshot(self, message: discord.Message, t0: float):
        import io
        from PIL import Image
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=75)
        buf.seek(0)
        embed = discord.Embed(title="🖥️ 当前屏幕截图", color=0x2ecc71, timestamp=datetime.now())
        embed.set_image(url="attachment://screen.jpg")
        embed.set_footer(text=self._footer(t0))
        await message.reply(embed=embed, file=discord.File(buf, filename="screen.jpg"))

    async def _ask_confirm(self, target, tool_name: str, args: dict) -> bool:
        """发送带按钮的确认消息，等待用户点击后立即删除（节省页面空间）。"""
        args_str = str(args)[:300]
        embed = discord.Embed(
            title="⚠️ 需要确认",
            description=f"即将执行 `{tool_name}`\n```{args_str}```",
            color=0xe67e22,
        )
        view = ConfirmView(timeout=30)
        confirm_msg = await target.send(embed=embed, view=view)
        await view.wait()
        try:
            await confirm_msg.delete()
        except Exception:
            pass
        return view.value is True

    # ── 思考动画帧（braille 圆环旋转，视觉上类似 Claude thinking）──────────
    _SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _make_status_view(self, thinking: bool, tools_count: int) -> discord.ui.View:
        """构造状态栏 View：思考/执行指示按钮 + 可选的工具调用计数按钮。"""
        view = discord.ui.View(timeout=None)
        btn_label = "思考中" if thinking else "执行中"
        btn_style = discord.ButtonStyle.primary if thinking else discord.ButtonStyle.secondary
        view.add_item(discord.ui.Button(label=btn_label, style=btn_style, disabled=True))
        if tools_count > 0:
            view.add_item(discord.ui.Button(
                label=f"⚙  已调用 {tools_count} 个工具",
                style=discord.ButtonStyle.secondary,
                disabled=True,
            ))
        return view

    async def _spin_status(
        self,
        msg: discord.Message,
        label: str,
        stop: asyncio.Event,
        t0: float,
        *,
        thinking: bool = True,
        tools_count: int = 0,
    ):
        """在 msg 上播放 braille 旋转动画（只更新 embed，不重建 View，避免 Discord 限速）。"""
        color = 0x5865f2 if thinking else 0x3498db
        n = len(self._SPIN_FRAMES)
        i = 0
        while not stop.is_set():
            frame = self._SPIN_FRAMES[i % n]
            embed = discord.Embed(description=f"{frame}  {label}…", color=color)
            embed.set_footer(text=self._footer(t0))
            try:
                await msg.edit(embed=embed)   # 不传 view=，保留现有按钮不重建
            except Exception:
                pass
            i += 1
            await asyncio.sleep(0.4)

    # 用于在队列中传递特殊控制信号（不能是 None，None 是结束符）
    _CLEAR_SENTINEL = object()

    async def _stream_response(self, msg: discord.Message, brain: Brain, t0: float) -> tuple:
        """将 LLM 流式回复写入已有消息 msg（同时移除状态按钮）。
        若 LLM 先输出文字后切换为工具调用，会立即撤回草稿文字、还原思考状态。
        返回 (action, accumulated_text)。"""
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        action_holder: list = []

        def run_stream():
            def on_chunk(chunk: str):
                loop.call_soon_threadsafe(q.put_nowait, chunk)

            def on_clear():
                # LLM 切换到工具调用模式 → 通知主协程清除已显示的草稿文字
                loop.call_soon_threadsafe(q.put_nowait, StarBotClient._CLEAR_SENTINEL)

            action_holder.append(
                brain._call_native_stream(on_chunk=on_chunk, on_clear=on_clear)
            )
            loop.call_soon_threadsafe(q.put_nowait, None)

        stream_task = asyncio.create_task(asyncio.to_thread(run_stream))
        accumulated = ""
        started = False
        last_edit = 0.0

        while True:
            chunk = await q.get()
            if chunk is None:
                break

            # ── 清除信号：LLM 已切换到工具调用，草稿文字作废 ────────────────
            if chunk is StarBotClient._CLEAR_SENTINEL:
                if accumulated:
                    log.debug("_stream_response: LLM 切换到工具调用，清除已流式显示的草稿文字（%d 字符）", len(accumulated))
                    accumulated = ""
                    started = False
                    # 还原消息为思考动画状态，等待工具执行动画接管
                    try:
                        await msg.edit(
                            embed=discord.Embed(description="⠋  思考中…", color=0x5865f2),
                            view=None,
                        )
                    except Exception:
                        pass
                continue

            if not started:
                started = True
                try:
                    await msg.edit(view=None)   # 文字开始输出时移除旋转按钮
                except Exception:
                    pass
            accumulated += chunk
            now = loop.time()
            if now - last_edit >= 0.4:
                embed = discord.Embed(description=accumulated[:4000] + " ▌", color=0x9b59b6)
                embed.set_footer(text=self._footer(t0))
                try:
                    await msg.edit(embed=embed)
                except Exception:
                    pass
                last_edit = now

        await stream_task

        # ── 兜底过滤：纯数字序列或大多数行是数字 → 视为无效草稿丢弃 ────────
        if accumulated:
            lines = [l.strip() for l in accumulated.strip().splitlines() if l.strip()]
            if len(lines) >= 5:
                digit_lines = sum(1 for l in lines if l.isdigit())
                if digit_lines / len(lines) > 0.7:
                    log.warning(
                        "_stream_response: 兜底过滤了垃圾输出（%d/%d 行为纯数字）",
                        digit_lines, len(lines),
                    )
                    accumulated = ""
                    try:
                        await msg.edit(
                            embed=discord.Embed(description="⠋  思考中…", color=0x5865f2),
                            view=None,
                        )
                    except Exception:
                        pass

        if accumulated:
            embed = discord.Embed(
                description=accumulated[:4000], color=0x9b59b6, timestamp=datetime.now()
            )
            embed.set_footer(text=self._footer(t0))
            try:
                await msg.edit(embed=embed, view=None)
            except Exception:
                pass

        return action_holder[0] if action_holder else None, accumulated

    @staticmethod
    def _parse_plan_steps(text: str) -> list[str]:
        """从 LLM 规划文本中提取编号步骤列表。"""
        # 优先匹配 ①②③ 圆圈数字
        steps = re.findall(r'[①②③④⑤⑥⑦⑧⑨⑩]\s*([^①②③④⑤⑥⑦⑧⑨⑩\n]{3,80})', text)
        if len(steps) >= 2:
            return [s.strip().rstrip('，,。 ') for s in steps]
        # 其次匹配 1. / 1、/ (1) 格式
        steps = re.findall(r'(?:^|\n)\s*(?:\d+[.、．]|\(\d+\))\s*(.{3,80})', text)
        if len(steps) >= 2:
            return [s.strip() for s in steps]
        return []

    async def _handle(self, message: discord.Message, t0: float, brain: Brain, session_key: int):
        text = message.content.strip()
        self._active_tasks[message.id] = text
        reply_target = message.channel
        active_session_key = session_key
        tools_called = 0

        # ── 初始状态消息（思考中 + 旋转动画）────────────────────────────────
        cur_msg: discord.Message = await reply_target.send(
            embed=discord.Embed(description="◐  思考中…", color=0x5865f2),
            view=self._make_status_view(thinking=True, tools_count=0),
        )
        anim_stop = asyncio.Event()
        anim_task: asyncio.Task = asyncio.create_task(
            self._spin_status(cur_msg, "思考中", anim_stop, t0, thinking=True)
        )
        keep_cur = False  # cur_msg 是否已包含需保留的 AI 文本

        # 关闭当前动画（闭包引用变量，始终操作最新的 anim_stop/anim_task）
        async def stop_anim():
            anim_stop.set()
            if not anim_task.done():
                anim_task.cancel()
                try:
                    await anim_task
                except asyncio.CancelledError:
                    pass

        async def safe_delete(m: discord.Message):
            try:
                await m.delete()
            except Exception:
                pass

        try:
            for i in range(30):
                # ── 获取 LLM 下一步动作 ───────────────────────────────────────
                try:
                    await stop_anim()
                    if i == 0:
                        # 第一轮：流式输出到 cur_msg
                        action, plan_text = await self._stream_response(cur_msg, brain, t0)
                        if plan_text:
                            keep_cur = True   # AI 输出了文字 → 这条消息要保留
                    else:
                        action = await asyncio.to_thread(brain._call_native)
                except asyncio.CancelledError:
                    try:
                        await cur_msg.edit(
                            embed=discord.Embed(description="✋ 已停止", color=0xe74c3c),
                            view=None,
                        )
                    except Exception:
                        pass
                    keep_cur = True
                    break
                except Exception as e:
                    try:
                        await cur_msg.edit(
                            embed=discord.Embed(description=f"❌ API 异常：{e}", color=0xe74c3c),
                            view=None,
                        )
                    except Exception:
                        pass
                    keep_cur = True
                    break

                # ── 无动作 → 结束 ─────────────────────────────────────────────
                if not action:
                    if not keep_cur:
                        await safe_delete(cur_msg)
                    break

                # ── 纯文字回复（非工具调用）──────────────────────────────────
                if isinstance(action, dict) and "text" in action and "name" not in action:
                    if i > 0:
                        # 追加一条新的永久消息
                        embed = discord.Embed(
                            description=action["text"][:4000], color=0x9b59b6, timestamp=datetime.now()
                        )
                        embed.set_footer(text=self._footer(t0))
                        await reply_target.send(embed=embed)
                        if not keep_cur:
                            await safe_delete(cur_msg)
                    break

                # ── 工具调用 ──────────────────────────────────────────────────
                actions = action if isinstance(action, list) else [action]

                # 危险工具确认
                safe_actions: list[dict] = []
                for a in actions:
                    if a.get("name") in _CONFIRM_TOOLS:
                        try:
                            args_dict = json.loads(a.get("arguments", "{}"))
                        except Exception:
                            args_dict = {}
                        if await self._ask_confirm(reply_target, a["name"], args_dict):
                            safe_actions.append(a)
                        else:
                            brain._feed_native_result(
                                a.get("id", ""), {"ok": False, "result": "用户取消了该操作"}, None
                            )
                    else:
                        safe_actions.append(a)
                if not safe_actions:
                    continue

                tools_called += len(safe_actions)
                tool_names = ", ".join(a.get("name", "") for a in safe_actions)

                # 若 cur_msg 已有 AI 文字 → 另建临时工具状态消息；否则复用 cur_msg
                if keep_cur:
                    tool_msg: discord.Message = await reply_target.send(
                        embed=discord.Embed(description=f"◐  执行 {tool_names}…", color=0x3498db),
                        view=self._make_status_view(thinking=False, tools_count=tools_called),
                    )
                else:
                    tool_msg = cur_msg

                # 启动工具执行动画
                anim_stop = asyncio.Event()
                anim_task = asyncio.create_task(
                    self._spin_status(
                        tool_msg, f"执行 {tool_names}", anim_stop, t0,
                        thinking=False, tools_count=tools_called,
                    )
                )

                # 执行工具
                try:
                    results = await asyncio.gather(
                        *[asyncio.to_thread(execute, a) for a in safe_actions]
                    )
                finally:
                    await stop_anim()

                # 处理结果并喂给 brain
                done_result = None
                last_image = None
                for a, result in zip(safe_actions, results):
                    img = result.get("image")
                    feed = {k: v for k, v in result.items() if k != "image"}
                    if not result.get("ok", True):
                        brain._fail_streak += 1
                        if brain._fail_streak == 1:
                            feed["result"] = feed.get("result", "") + \
                                "\n\n[系统提示] 此步骤失败，请分析原因并尝试不同方案重试。"
                        elif brain._fail_streak == 2:
                            feed["result"] = feed.get("result", "") + \
                                "\n\n[系统提示] 这是第2次失败，请换一种完全不同的方案，这是最后一次自动重试机会。"
                        else:
                            feed["result"] = feed.get("result", "") + \
                                "\n\n[系统提示] 已连续失败3次，请停止尝试，向用户说明情况并询问如何继续。"
                            brain._fail_streak = 0
                    else:
                        brain._fail_streak = 0
                    brain._feed_native_result(a.get("id", ""), feed, img)
                    if result.get("done"):
                        done_result = result
                        last_image = img
                    elif img:
                        last_image = img

                # ── 工具执行完毕 → 删除工具状态消息 ─────────────────────────
                await safe_delete(tool_msg)
                if not keep_cur:
                    cur_msg = None  # tool_msg 即 cur_msg，已删除

                if done_result:
                    result_text = f"✅ {done_result.get('result', '')}"
                    await self._edit_or_reply(reply_target, None, result_text, last_image, t0)
                    break

                # ── 继续下一轮：建新的"思考中"状态消息 ──────────────────────
                cur_msg = await reply_target.send(
                    embed=discord.Embed(description="◐  思考中…", color=0x5865f2),
                    view=self._make_status_view(thinking=True, tools_count=tools_called),
                )
                keep_cur = False
                anim_stop = asyncio.Event()
                anim_task = asyncio.create_task(
                    self._spin_status(
                        cur_msg, "思考中", anim_stop, t0,
                        thinking=True, tools_count=tools_called,
                    )
                )

        finally:
            try:
                anim_stop.set()
                if not anim_task.done():
                    anim_task.cancel()
            except Exception:
                pass
            self._active_tasks.pop(message.id, None)
            self._active_task_handles.pop(message.id, None)
            brain_to_save = self._session_brains.get(active_session_key)
            if brain_to_save:
                self._persist_session(active_session_key, brain_to_save)
            if self._active_session_handles.get(active_session_key) is asyncio.current_task():
                self._active_session_handles.pop(active_session_key, None)
            # 频道会话 brain 保持常驻，下次消息继续同一上下文

    @staticmethod
    def _send_fn(target):
        # Channel 和 Thread 都有 .send()，统一使用
        return target.send

    async def _edit_or_reply(self, target, target_msg, text: str, image_path: str = None, t0: float = None):
        if t0 is None:
            t0 = time.time()
        fname = os.path.basename(image_path) if image_path else "result.jpg"
        embed = discord.Embed(color=0x9b59b6, timestamp=datetime.now())
        embed.set_footer(text=self._footer(t0))
        if image_path:
            embed.description = text[:4000] if len(text) <= 4000 else text[:4000] + "…"
            embed.set_image(url=f"attachment://{fname}")
            await self._send_fn(target)(embed=embed, file=discord.File(image_path, filename=fname))
            return
        if target_msg:
            try:
                embed.description = text[:4000] if len(text) <= 4000 else text[:4000] + "…"
                await target_msg.edit(embed=embed)
                if len(text) > 4000:
                    await self._send_chunks(target, text[4000:])
                return
            except Exception:
                pass
        embed.description = text[:4000] if len(text) <= 4000 else text[:4000] + "…"
        await self._send_fn(target)(embed=embed)
        if len(text) > 4000:
            await self._send_chunks(target, text[4000:])

    async def _send_chunks(self, target, text: str):
        """Send remaining text in 4000-char chunks."""
        for i in range(0, len(text), 4000):
            await target.send(text[i:i+4000])

    async def _cmd_stop(self, message: discord.Message):
        tasks = set(self._active_task_handles.values()) | set(self._active_session_handles.values())
        if not tasks:
            await message.reply("当前没有正在执行的任务")
            return
        count = len(tasks)
        for task in tasks:
            task.cancel()
        self._active_task_handles.clear()
        self._active_session_handles.clear()
        self._active_tasks.clear()
        await message.reply(f"✋ 已停止 {count} 个任务")

    async def _cmd_model(self, message: discord.Message, t0: float):
        try:
            resp = await asyncio.to_thread(lambda: self._llm.client.with_options(timeout=8).models.list())
            models = [m.id for m in resp.data]
        except Exception as e:
            await message.reply(f"获取模型列表失败：{e}\n直接发送模型名称也可以切换，如：`/model gpt-4o`")
            return
        names = "\n".join(f"`{i+1}.` {m}" for i, m in enumerate(models))
        if len(names) > 4000:
            names = names[:4000] + "\n..."
        embed = discord.Embed(title="可用模型", description=names, color=0x3498db)
        embed.add_field(name="当前模型", value=f"`{config.LLM_MODEL}`")
        embed.set_footer(text="输入序号切换模型")
        await message.reply(embed=embed)
        self._model_list[message.author.id] = models

    async def _cmd_skill_list(self, message: discord.Message):
        skills = _skill_manager.list_skills()
        if not skills:
            embed = discord.Embed(
                title="🔌 已安装的 Skills",
                description="暂无已安装的 skill\n\n用 `/skill install <URL>` 安装",
                color=0x3498db,
            )
        else:
            embed = discord.Embed(title="🔌 已安装的 Skills", color=0x3498db)
            for s in skills:
                tools_str = "、".join(f"`{t}`" for t in s["tools"]) or "（无工具）"
                embed.add_field(
                    name=f"{s['name']} v{s['version']}",
                    value=f"{s['description']}\n工具：{tools_str}",
                    inline=False,
                )
        embed.set_footer(text="/skill install <URL>  |  /skill remove <name>  |  /skill reload")
        await message.reply(embed=embed)

    async def _cmd_skill_install(self, message: discord.Message, source: str):
        if not source:
            await message.reply("用法：`/skill install <URL 或 本地路径>`")
            return
        thinking = await message.reply(
            embed=discord.Embed(description="⣾ 安装中…", color=0x95a5a6)
        )
        ok, msg = await asyncio.to_thread(_skill_manager.install, source)
        color = 0x2ecc71 if ok else 0xe74c3c
        icon = "✅" if ok else "❌"
        embed = discord.Embed(description=f"{icon} {msg}", color=color)
        if ok:
            embed.set_footer(text="新工具将在下一次对话中生效")
        await thinking.edit(embed=embed)

    async def _cmd_skill_remove(self, message: discord.Message, name: str):
        if not name:
            await message.reply("用法：`/skill remove <skill名称>`")
            return
        ok, msg = _skill_manager.remove(name)
        color = 0x2ecc71 if ok else 0xe74c3c
        embed = discord.Embed(description=f"{'✅' if ok else '❌'} {msg}", color=color)
        await message.reply(embed=embed)

    async def _cmd_skill_reload(self, message: discord.Message):
        _skill_manager.reload()
        skills = _skill_manager.list_skills()
        embed = discord.Embed(
            description=f"✅ 已重新加载，共 {len(skills)} 个 skill",
            color=0x2ecc71,
        )
        await message.reply(embed=embed)

    async def _cmd_memory(self, message: discord.Message, text: str, t0: float):
        """Handle /memory [list|search|delete|stats] [arg]."""
        mem = MemoryStore()
        parts = text.split(maxsplit=2)
        sub = parts[1].lower() if len(parts) > 1 else "list"
        arg = parts[2] if len(parts) > 2 else ""

        if sub == "stats":
            stats = mem.stats()
            lines = "\n".join(f"**{cat}**: {cnt}" for cat, cnt in stats.items()) or "暂无记忆"
            total = sum(stats.values())
            embed = discord.Embed(title="🧠 记忆统计", description=lines, color=0x3498db)
            embed.set_footer(text=f"共 {total} 条 | {self._footer(t0)}")

        elif sub == "search":
            if not arg:
                await message.reply("用法：`/memory search <关键词>`")
                return
            results = mem.search_multi(arg, limit=8)
            if not results:
                embed = discord.Embed(description=f"未找到包含 `{arg}` 的记忆", color=0xe74c3c)
            else:
                lines = [
                    f"`#{r['id']}` [{r['category']}] {r['content'][:120].replace(chr(10), ' ')}"
                    for r in results
                ]
                embed = discord.Embed(title=f"🔍 搜索：{arg}", description="\n".join(lines), color=0x3498db)
            embed.set_footer(text=self._footer(t0))

        elif sub == "delete":
            if not arg or not arg.isdigit():
                await message.reply("用法：`/memory delete <ID>`")
                return
            ok = mem.delete_by_id(int(arg))
            embed = discord.Embed(
                description=f"{'✅ 已删除' if ok else '❌ 删除失败'} ID={arg}",
                color=0x2ecc71 if ok else 0xe74c3c,
            )
            embed.set_footer(text=self._footer(t0))

        else:
            # "list" or a category name like "preference", "knowledge", etc.
            category = "" if sub == "list" else sub
            rows = mem.list_by_category(category, limit=15)
            if not rows:
                desc = "暂无记忆" + (f" (分类: {category})" if category else "")
                embed = discord.Embed(description=desc, color=0x95a5a6)
            else:
                lines = [
                    f"`#{r['id']}` [{r['category']}] ★{r['importance']} {r['content'][:100].replace(chr(10), ' ')}"
                    for r in rows
                ]
                title = "🧠 记忆列表" + (f" — {category}" if category else "")
                embed = discord.Embed(title=title, description="\n".join(lines), color=0x3498db)
            embed.set_footer(text=f"/memory search <词>  |  /memory delete <ID>  |  /memory stats | {self._footer(t0)}")

        await message.reply(embed=embed)

    async def _cmd_reset(self, message: discord.Message, session_key: int, t0: float):
        """Clear current session brain and delete the persisted session file."""
        self._session_brains.pop(session_key, None)
        f = self._session_file(session_key)
        try:
            if f.exists():
                f.unlink()
        except Exception:
            pass
        embed = discord.Embed(description="✅ 当前会话已重置，上下文已清空", color=0x2ecc71)
        embed.set_footer(text=self._footer(t0))
        await message.reply(embed=embed)

    async def _cmd_usage(self, message: discord.Message, brain, t0: float):
        """Show token usage for the current session brain."""
        if brain is None:
            embed = discord.Embed(description="当前没有活跃会话，无 token 统计", color=0x95a5a6)
        else:
            u = brain.usage
            desc = (
                f"**输入 tokens:** {u.get('input', 0):,}\n"
                f"**输出 tokens:** {u.get('output', 0):,}\n"
                f"**API 调用次数:** {u.get('calls', 0)}"
            )
            embed = discord.Embed(title="📊 Token 用量（本会话）", description=desc, color=0x3498db)
        embed.set_footer(text=self._footer(t0))
        await message.reply(embed=embed)

    async def _cmd_tasks(self, message: discord.Message, t0: float):
        """Show background tasks summary."""
        summary = _task_mgr.summary()
        embed = discord.Embed(
            title="📋 后台任务",
            description=summary or "暂无后台任务",
            color=0x3498db,
        )
        embed.set_footer(text=self._footer(t0))
        await message.reply(embed=embed)

    async def _cmd_config(self, message: discord.Message, text: str, t0: float):
        """View or set editable config values."""
        parts = text.split(maxsplit=2)
        EDITABLE = {"LLM_MODEL", "LLM_API_BASE", "LLM_API_KEY", "DISCORD_PROXY"}

        if len(parts) == 1:
            lines = [f"`{k}`: `{getattr(config, k, '')}`" for k in sorted(EDITABLE)]
            embed = discord.Embed(title="⚙️ 配置项", description="\n".join(lines), color=0x3498db)
            embed.set_footer(text="/config <key> <value> 修改 | " + self._footer(t0))
        elif len(parts) == 2:
            k = parts[1].upper()
            val = getattr(config, k, "（未知配置项）")
            embed = discord.Embed(description=f"`{k}` = `{val}`", color=0x3498db)
            embed.set_footer(text=self._footer(t0))
        else:
            k, v = parts[1].upper(), parts[2]
            if k not in EDITABLE:
                await message.reply(f"❌ 不允许修改 `{k}`，可修改项：{', '.join(sorted(EDITABLE))}")
                return
            setattr(config, k, v)
            if k in ("LLM_MODEL", "LLM_API_BASE", "LLM_API_KEY"):
                self._llm = UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)
            _save_state({k: v})
            embed = discord.Embed(description=f"✅ `{k}` 已更新为 `{v}`", color=0x2ecc71)
            embed.set_footer(text=self._footer(t0))

        await message.reply(embed=embed)

    async def _cmd_rollback(self, message: discord.Message, text: str, t0: float):
        """Undo the last N file write/delete operations."""
        parts = text.split()
        n = 1
        if len(parts) > 1 and parts[1].isdigit():
            n = max(1, min(10, int(parts[1])))
        thinking = await message.reply(
            embed=discord.Embed(description=f"⣾ 正在撤销最近 {n} 次文件操作…", color=0x95a5a6)
        )
        msgs = await asyncio.to_thread(undo_last, n)
        result = "\n".join(msgs)
        color = 0x2ecc71 if any("✅" in m for m in msgs) else 0xe74c3c
        embed = discord.Embed(title="⏪ 撤销结果", description=result[:4000], color=color)
        embed.set_footer(text=self._footer(t0))
        await thinking.edit(embed=embed)

    async def _embed_reply(self, target, text: str, image_path: str = None, t0: float = None):
        if t0 is None:
            t0 = time.time()
        fname = os.path.basename(image_path) if image_path else "result.jpg"
        embed = discord.Embed(description=text[:4000], color=0x9b59b6, timestamp=datetime.now())
        embed.set_footer(text=self._footer(t0))
        if image_path:
            embed.set_image(url=f"attachment://{fname}")
            await self._send_fn(target)(embed=embed, file=discord.File(image_path, filename=fname))
        else:
            await self._send_fn(target)(embed=embed)
        if len(text) > 4000:
            await self._send_chunks(target, text[4000:])


def start_discord():
    proxy = config.DISCORD_PROXY or None
    client = StarBotClient(intents=intents, proxy=proxy)
    client.run(config.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    start_discord()
