"""Condition monitoring skill — watches stocks/websites/custom conditions and
   sends Discord notifications when triggered, with optional LLM advice.

Architecture:
    Background thread polls at given interval → condition met →
    core.notifier.notify() → asyncio.run_coroutine_threadsafe → Discord embed
"""

META = {
    "name": "monitor",
    "version": "1.0.0",
    "description": "后台条件监控：股价触达阈值、网页关键词出现、自定义条件——触发时直接在 Discord 发送提醒和 AI 建议",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "watch_stock",
            "description": (
                "在后台监控一支股票价格，满足条件时立即在 Discord 发出提醒并给出 AI 投资建议。"
                "条件类型：gt（价格高于）/ lt（价格低于）/ "
                "crosses_above（向上穿越）/ crosses_below（向下穿越）/ "
                "change_up（涨幅%超过）/ change_down（跌幅%超过）"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码，如 AAPL、600519.SS、0700.HK",
                    },
                    "condition": {
                        "type": "string",
                        "description": "触发条件：gt / lt / crosses_above / crosses_below / change_up / change_down",
                    },
                    "threshold": {
                        "type": "number",
                        "description": "阈值（价格或涨跌幅%）",
                    },
                    "interval_min": {
                        "type": "number",
                        "description": "检查间隔（分钟），默认 5，最小 1",
                        "default": 5,
                    },
                    "note": {
                        "type": "string",
                        "description": "触发时提醒的附加说明，如 '考虑买入'",
                        "default": "",
                    },
                    "give_advice": {
                        "type": "boolean",
                        "description": "触发时是否让 AI 给出投资建议，默认 true",
                        "default": True,
                    },
                    "once": {
                        "type": "boolean",
                        "description": "触发后是否自动停止监控（默认 true，避免反复提醒）",
                        "default": True,
                    },
                },
                "required": ["symbol", "condition", "threshold"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "watch_webpage",
            "description": (
                "在后台监控一个网页，当页面上出现或消失指定关键词时发 Discord 通知。"
                "适合监控商品上架、价格变化、公告发布等"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要监控的网页 URL"},
                    "keyword": {"type": "string", "description": "触发条件的关键词"},
                    "condition": {
                        "type": "string",
                        "description": "appears（关键词出现时触发）或 disappears（消失时触发），默认 appears",
                        "default": "appears",
                    },
                    "interval_min": {
                        "type": "number",
                        "description": "检查间隔（分钟），默认 10",
                        "default": 10,
                    },
                    "note": {
                        "type": "string",
                        "description": "触发时的附加说明",
                        "default": "",
                    },
                    "once": {
                        "type": "boolean",
                        "description": "触发后是否自动停止，默认 true",
                        "default": True,
                    },
                },
                "required": ["url", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "watch_price_range",
            "description": "监控股票在指定价格区间内运动：跌出区间下沿或涨出区间上沿时提醒",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码"},
                    "low": {"type": "number", "description": "区间下沿价格"},
                    "high": {"type": "number", "description": "区间上沿价格"},
                    "interval_min": {"type": "number", "description": "检查间隔分钟，默认 5", "default": 5},
                    "give_advice": {"type": "boolean", "description": "是否给出建议，默认 true", "default": True},
                },
                "required": ["symbol", "low", "high"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_monitors",
            "description": "列出所有正在运行的监控任务",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_monitor",
            "description": "停止一个或全部监控任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "monitor_id": {
                        "type": "string",
                        "description": "监控 ID（从 list_monitors 获取），传 'all' 停止全部",
                    },
                },
                "required": ["monitor_id"],
            },
        },
    },
]

import logging
import threading
import time

log = logging.getLogger(__name__)

_lock = threading.Lock()
_monitors: dict[str, dict] = {}
_counter = 0

_YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _next_id(prefix: str) -> str:
    global _counter
    _counter += 1
    return f"{prefix}{_counter:03d}"


def _get_proxies():
    try:
        from config import config
        proxy = getattr(config, "PROXY", None)
        if proxy:
            return {"http": proxy, "https": proxy}
    except Exception:
        pass
    return None


# ── Stock price fetcher ───────────────────────────────────────────────────────

def _fetch_price(symbol: str) -> float | None:
    import requests
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"interval": "1d", "range": "1d"},
            headers=_YF_HEADERS,
            proxies=_get_proxies(),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        res = data.get("chart", {}).get("result")
        if not res:
            return None
        return float(res[0]["meta"].get("regularMarketPrice", 0))
    except Exception as e:
        log.warning("Price fetch failed for %s: %s", symbol, e)
        return None


# ── LLM advice ───────────────────────────────────────────────────────────────

def _get_advice(symbol: str, price: float, condition: str, threshold: float, note: str) -> str:
    try:
        from config import config
        from core.adapter import UniversalLLM
        llm = UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)
        prompt = (
            f"股票 {symbol} 当前价格 {price:.4f}，刚刚触发了监控条件"
            f"（{condition} 阈值 {threshold}）。"
            + (f"用户备注：{note}。" if note else "")
            + "\n\n请从以下角度给出简洁的参考意见（3-5句话，不超过200字）：\n"
            "1. 这个价位在技术面上意味着什么\n"
            "2. 短期操作建议（买入/卖出/持有/观望）\n"
            "3. 主要风险提示\n"
            "⚠️ 最后注明：仅供参考，不构成投资建议。"
        )
        return llm.chat(prompt)
    except Exception as e:
        log.warning("Advice generation failed: %s", e)
        return ""


# ── Condition checker ─────────────────────────────────────────────────────────

def _check_stock_condition(
    price: float,
    prev_price: float | None,
    start_price: float,
    condition: str,
    threshold: float,
) -> bool:
    if condition == "gt":
        return price > threshold
    if condition == "lt":
        return price < threshold
    if condition == "crosses_above":
        return prev_price is not None and prev_price < threshold <= price
    if condition == "crosses_below":
        return prev_price is not None and prev_price > threshold >= price
    if condition == "change_up":
        return (price - start_price) / start_price * 100 >= threshold
    if condition == "change_down":
        return (start_price - price) / start_price * 100 >= threshold
    return False


# ── Monitor threads ───────────────────────────────────────────────────────────

def _stock_monitor_thread(mid: str) -> None:
    from core.notifier import notify

    with _lock:
        cfg = dict(_monitors[mid])

    symbol = cfg["symbol"]
    condition = cfg["condition"]
    threshold = cfg["threshold"]
    interval_s = cfg["interval_min"] * 60
    note = cfg.get("note", "")
    give_advice = cfg.get("give_advice", True)
    once = cfg.get("once", True)

    start_price = _fetch_price(symbol)
    if start_price is None:
        notify(
            f"⚠️ 监控 [{mid}] 启动失败：无法获取 {symbol} 的价格，请检查股票代码",
            title="监控错误",
            color=0xe74c3c,
        )
        with _lock:
            if mid in _monitors:
                _monitors[mid]["active"] = False
        return

    prev_price: float | None = None
    triggered_count = 0

    log.info("Monitor [%s] started: %s %s %s, every %.1f min", mid, symbol, condition, threshold, cfg["interval_min"])

    while True:
        # Check if still active
        with _lock:
            if mid not in _monitors or not _monitors[mid].get("active"):
                break

        time.sleep(interval_s)

        # Re-check active after sleep
        with _lock:
            if mid not in _monitors or not _monitors[mid].get("active"):
                break

        price = _fetch_price(symbol)
        if price is None:
            continue

        triggered = _check_stock_condition(price, prev_price, start_price, condition, threshold)

        if triggered:
            triggered_count += 1
            chg = (price - start_price) / start_price * 100
            chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"

            cond_desc = {
                "gt": f"价格高于 {threshold}",
                "lt": f"价格低于 {threshold}",
                "crosses_above": f"向上穿越 {threshold}",
                "crosses_below": f"向下穿越 {threshold}",
                "change_up": f"涨幅超过 {threshold}%",
                "change_down": f"跌幅超过 {threshold}%",
            }.get(condition, condition)

            body_lines = [
                f"**股票：** {symbol}",
                f"**当前价格：** {price:.4f}",
                f"**触发条件：** {cond_desc}",
                f"**较监控开始：** {chg_str}（开始价 {start_price:.4f}）",
            ]
            if note:
                body_lines.append(f"**备注：** {note}")

            advice = _get_advice(symbol, price, condition, threshold, note) if give_advice else ""
            if advice:
                body_lines += ["", "💡 **AI 参考建议**", advice]

            notify(
                "\n".join(body_lines),
                title=f"📈 监控触发 [{mid}]：{symbol}",
                color=0x2ecc71 if "up" in condition or condition in ("gt", "crosses_above") else 0xe74c3c,
                footer=f"监控 {mid} | 已触发 {triggered_count} 次",
            )

            if once:
                with _lock:
                    if mid in _monitors:
                        _monitors[mid]["active"] = False
                log.info("Monitor [%s] auto-stopped after trigger", mid)
                break

        with _lock:
            if mid in _monitors:
                _monitors[mid]["last_price"] = price
                _monitors[mid]["last_check"] = time.time()

        prev_price = price

    log.info("Monitor [%s] thread exiting", mid)


def _webpage_monitor_thread(mid: str) -> None:
    import requests
    from core.notifier import notify
    from html.parser import HTMLParser
    import re

    with _lock:
        cfg = dict(_monitors[mid])

    url = cfg["url"]
    keyword = cfg["keyword"]
    condition = cfg["condition"]  # "appears" or "disappears"
    interval_s = cfg["interval_min"] * 60
    note = cfg.get("note", "")
    once = cfg.get("once", True)

    class _Strip(HTMLParser):
        def __init__(self):
            super().__init__()
            self._parts = []
        def handle_data(self, data):
            t = data.strip()
            if t:
                self._parts.append(t)
        def text(self):
            return " ".join(self._parts)

    def _page_has_keyword(u: str) -> bool | None:
        try:
            r = requests.get(u, timeout=15, proxies=_get_proxies(),
                             headers={"User-Agent": "Mozilla/5.0"})
            p = _Strip()
            p.feed(r.text)
            return keyword.lower() in p.text().lower()
        except Exception as e:
            log.warning("Webpage fetch error [%s]: %s", mid, e)
            return None

    # Initial state
    initial = _page_has_keyword(url)
    prev_state = initial
    triggered_count = 0

    log.info("Monitor [%s] webpage started: %s keyword='%s' cond=%s", mid, url, keyword, condition)

    while True:
        with _lock:
            if mid not in _monitors or not _monitors[mid].get("active"):
                break

        time.sleep(interval_s)

        with _lock:
            if mid not in _monitors or not _monitors[mid].get("active"):
                break

        has_kw = _page_has_keyword(url)
        if has_kw is None:
            continue

        triggered = (condition == "appears" and has_kw and not prev_state) or \
                    (condition == "disappears" and not has_kw and prev_state)

        if triggered:
            triggered_count += 1
            event = "出现" if condition == "appears" else "消失"
            body = (
                f"**URL：** {url}\n"
                f"**关键词「{keyword}」已{event}**\n"
            )
            if note:
                body += f"**备注：** {note}\n"

            notify(
                body,
                title=f"🌐 网页监控触发 [{mid}]",
                color=0x3498db,
                footer=f"监控 {mid} | 已触发 {triggered_count} 次",
            )
            if once:
                with _lock:
                    if mid in _monitors:
                        _monitors[mid]["active"] = False
                break

        with _lock:
            if mid in _monitors:
                _monitors[mid]["last_check"] = time.time()

        prev_state = has_kw

    log.info("Monitor [%s] thread exiting", mid)


def _range_monitor_thread(mid: str) -> None:
    from core.notifier import notify

    with _lock:
        cfg = dict(_monitors[mid])

    symbol = cfg["symbol"]
    low = cfg["low"]
    high = cfg["high"]
    interval_s = cfg["interval_min"] * 60
    give_advice = cfg.get("give_advice", True)

    start_price = _fetch_price(symbol)
    if start_price is None:
        notify(f"⚠️ 区间监控 [{mid}] 无法获取 {symbol} 价格", title="监控错误")
        with _lock:
            if mid in _monitors:
                _monitors[mid]["active"] = False
        return

    log.info("Monitor [%s] range: %s [%s, %s] every %.1f min", mid, symbol, low, high, cfg["interval_min"])

    while True:
        with _lock:
            if mid not in _monitors or not _monitors[mid].get("active"):
                break

        time.sleep(interval_s)

        with _lock:
            if mid not in _monitors or not _monitors[mid].get("active"):
                break

        price = _fetch_price(symbol)
        if price is None:
            continue

        if price < low or price > high:
            direction = "突破上沿" if price > high else "跌破下沿"
            boundary = high if price > high else low
            chg = (price - start_price) / start_price * 100

            body_lines = [
                f"**股票：** {symbol}",
                f"**当前价：** {price:.4f}  {direction}（{boundary:.4f}）",
                f"**监控区间：** {low:.4f} ~ {high:.4f}",
                f"**较开始：** {chg:+.2f}%",
            ]
            advice = _get_advice(symbol, price, direction, boundary, "") if give_advice else ""
            if advice:
                body_lines += ["", "💡 **AI 参考建议**", advice]

            notify(
                "\n".join(body_lines),
                title=f"📊 区间突破 [{mid}]：{symbol}",
                color=0x2ecc71 if price > high else 0xe74c3c,
                footer=f"监控 {mid}",
            )
            with _lock:
                if mid in _monitors:
                    _monitors[mid]["active"] = False
            break

        with _lock:
            if mid in _monitors:
                _monitors[mid]["last_price"] = price
                _monitors[mid]["last_check"] = time.time()


# ── execute ───────────────────────────────────────────────────────────────────

def execute(name: str, args: dict) -> dict:

    if name == "watch_stock":
        symbol = args["symbol"].strip().upper()
        condition = args["condition"].strip().lower()
        threshold = float(args["threshold"])
        interval_min = max(1.0, float(args.get("interval_min", 5)))
        note = str(args.get("note", ""))
        give_advice = bool(args.get("give_advice", True))
        once = bool(args.get("once", True))

        valid_conditions = {"gt", "lt", "crosses_above", "crosses_below", "change_up", "change_down"}
        if condition not in valid_conditions:
            return {"ok": False, "result": f"无效条件，可选：{', '.join(valid_conditions)}"}

        mid = _next_id("S")
        with _lock:
            _monitors[mid] = {
                "id": mid,
                "type": "stock",
                "symbol": symbol,
                "condition": condition,
                "threshold": threshold,
                "interval_min": interval_min,
                "note": note,
                "give_advice": give_advice,
                "once": once,
                "started": time.time(),
                "last_price": None,
                "last_check": None,
                "active": True,
            }

        t = threading.Thread(target=_stock_monitor_thread, args=(mid,), daemon=True)
        t.start()
        with _lock:
            _monitors[mid]["thread"] = t

        cond_desc = {
            "gt": f"价格 > {threshold}",
            "lt": f"价格 < {threshold}",
            "crosses_above": f"向上穿越 {threshold}",
            "crosses_below": f"向下穿越 {threshold}",
            "change_up": f"涨幅 ≥ {threshold}%",
            "change_down": f"跌幅 ≥ {threshold}%",
        }[condition]

        return {
            "ok": True,
            "result": (
                f"✅ 股票监控已启动 [{mid}]\n"
                f"  股票：{symbol}\n"
                f"  条件：{cond_desc}\n"
                f"  检查间隔：每 {interval_min:.0f} 分钟\n"
                f"  触发后{'自动停止' if once else '继续监控'}\n"
                f"  触发时{'含 AI 建议' if give_advice else '无 AI 建议'}\n"
                f"  触发后将在 Discord 频道发送提醒"
            ),
        }

    if name == "watch_webpage":
        url = args["url"].strip()
        keyword = args["keyword"].strip()
        condition = args.get("condition", "appears").lower()
        interval_min = max(1.0, float(args.get("interval_min", 10)))
        note = str(args.get("note", ""))
        once = bool(args.get("once", True))

        mid = _next_id("W")
        with _lock:
            _monitors[mid] = {
                "id": mid,
                "type": "webpage",
                "url": url,
                "keyword": keyword,
                "condition": condition,
                "interval_min": interval_min,
                "note": note,
                "once": once,
                "started": time.time(),
                "last_check": None,
                "active": True,
            }

        t = threading.Thread(target=_webpage_monitor_thread, args=(mid,), daemon=True)
        t.start()
        with _lock:
            _monitors[mid]["thread"] = t

        return {
            "ok": True,
            "result": (
                f"✅ 网页监控已启动 [{mid}]\n"
                f"  URL：{url}\n"
                f"  条件：关键词「{keyword}」{condition}\n"
                f"  检查间隔：每 {interval_min:.0f} 分钟"
            ),
        }

    if name == "watch_price_range":
        symbol = args["symbol"].strip().upper()
        low = float(args["low"])
        high = float(args["high"])
        interval_min = max(1.0, float(args.get("interval_min", 5)))
        give_advice = bool(args.get("give_advice", True))

        if low >= high:
            return {"ok": False, "result": f"区间错误：low ({low}) 必须小于 high ({high})"}

        mid = _next_id("R")
        with _lock:
            _monitors[mid] = {
                "id": mid,
                "type": "range",
                "symbol": symbol,
                "low": low,
                "high": high,
                "interval_min": interval_min,
                "give_advice": give_advice,
                "started": time.time(),
                "last_price": None,
                "last_check": None,
                "active": True,
            }

        t = threading.Thread(target=_range_monitor_thread, args=(mid,), daemon=True)
        t.start()
        with _lock:
            _monitors[mid]["thread"] = t

        return {
            "ok": True,
            "result": (
                f"✅ 区间监控已启动 [{mid}]\n"
                f"  股票：{symbol}\n"
                f"  区间：{low} ~ {high}\n"
                f"  检查间隔：每 {interval_min:.0f} 分钟\n"
                f"  突破区间时发 Discord 提醒"
            ),
        }

    if name == "list_monitors":
        with _lock:
            monitors = dict(_monitors)

        if not monitors:
            return {"ok": True, "result": "当前没有运行中的监控任务"}

        now = time.time()
        lines = [f"📡 监控任务列表（共 {len(monitors)} 个）:", ""]
        for mid, m in sorted(monitors.items()):
            active = m.get("active", False)
            status = "🟢 运行中" if active else "🔴 已停止"
            elapsed = int(now - m.get("started", now))
            h, rem = divmod(elapsed, 3600)
            mins = rem // 60
            uptime = f"{h}h {mins:02d}m" if h else f"{mins}m"

            lines.append(f"  [{mid}] {status}  已运行 {uptime}")
            mtype = m.get("type", "")
            if mtype == "stock":
                lines.append(f"    股票 {m['symbol']}  条件: {m['condition']} {m['threshold']}  间隔: {m['interval_min']:.0f}min")
                if m.get("last_price"):
                    lines.append(f"    最新价: {m['last_price']:.4f}")
            elif mtype == "webpage":
                lines.append(f"    URL: {m['url'][:60]}")
                lines.append(f"    关键词: 「{m['keyword']}」 {m['condition']}")
            elif mtype == "range":
                lines.append(f"    股票 {m['symbol']}  区间: {m['low']} ~ {m['high']}")
            lines.append("")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "stop_monitor":
        mid = str(args["monitor_id"]).strip()

        if mid.lower() == "all":
            with _lock:
                stopped = []
                for m_id, m in list(_monitors.items()):
                    if m.get("active"):
                        m["active"] = False
                        stopped.append(m_id)
            if not stopped:
                return {"ok": True, "result": "当前没有运行中的监控"}
            return {"ok": True, "result": f"已停止全部 {len(stopped)} 个监控：{', '.join(stopped)}"}

        with _lock:
            m = _monitors.get(mid)
            if not m:
                return {"ok": False, "result": f"未找到监控 [{mid}]，用 list_monitors 查看"}
            m["active"] = False

        return {"ok": True, "result": f"✅ 监控 [{mid}] 已停止"}

    return {"ok": False, "result": f"Unknown tool: {name}"}
