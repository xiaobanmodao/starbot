"""Discord notification bridge — safely sends messages from background threads to Discord.

Usage in any skill or module:
    from core.notifier import notify
    notify("⚠️ 价格触发！AAPL 当前 $185.50")
    notify("标题", "内容正文", color=0x2ecc71)
"""

import asyncio
import datetime
import logging
import threading

log = logging.getLogger(__name__)

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_channel = None  # discord.TextChannel


def setup(loop: asyncio.AbstractEventLoop, channel) -> None:
    """Called by discord_client.on_ready() to register the event loop and channel."""
    global _loop, _channel
    with _lock:
        _loop = loop
        _channel = channel
    log.info("Notifier: registered Discord channel #%s", getattr(channel, "name", str(channel)))


def notify(
    text: str,
    title: str = "🔔 通知",
    color: int = 0xe74c3c,
    footer: str = "",
) -> bool:
    """Send a rich embed to Discord from any thread.

    Args:
        text:   Body text of the notification (max 4000 chars).
        title:  Embed title line.
        color:  Embed left-bar colour (hex int). Red=0xe74c3c, Green=0x2ecc71, Blue=0x3498db.
        footer: Optional footer text.

    Returns:
        True if the coroutine was scheduled, False if notifier not yet set up.
    """
    with _lock:
        loop = _loop
        ch = _channel

    if not (loop and ch):
        log.warning("Notifier: not set up yet, message dropped: %.60s", text)
        return False

    async def _do() -> None:
        import discord
        try:
            embed = discord.Embed(
                title=title,
                description=text[:4000],
                color=color,
                timestamp=datetime.datetime.utcnow(),
            )
            if footer:
                embed.set_footer(text=footer)
            await ch.send(embed=embed)
        except Exception as e:
            log.error("Notifier: send failed: %s", e)

    asyncio.run_coroutine_threadsafe(_do(), loop)
    return True


def notify_plain(text: str) -> bool:
    """Send a plain-text message (no embed)."""
    with _lock:
        loop = _loop
        ch = _channel

    if not (loop and ch):
        return False

    async def _do() -> None:
        try:
            await ch.send(text[:2000])
        except Exception as e:
            log.error("Notifier: plain send failed: %s", e)

    asyncio.run_coroutine_threadsafe(_do(), loop)
    return True
