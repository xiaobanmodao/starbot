"""Stock market skill — Yahoo Finance (no API key needed)."""

META = {
    "name": "stock",
    "version": "1.0.0",
    "description": "股票/ETF/指数行情查询（Yahoo Finance，无需 API Key，支持 A股/港股/美股）",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": (
                "查询股票/ETF/指数的实时价格、涨跌幅、成交量等行情数据。"
                "A股代码格式：600519.SS（上交所）/ 000001.SZ（深交所）；"
                "港股：0700.HK；美股：AAPL；"
                "指数：000001.SS（上证）、^GSPC（S&P500）、^HSI（恒生）"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码，如 AAPL、600519.SS、0700.HK",
                    },
                    "details": {
                        "type": "boolean",
                        "description": "是否返回详细指标（市值、PE、52周高低），默认 false",
                        "default": False,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_stock",
            "description": "按公司名或关键词搜索股票代码，如输入'茅台'找到 600519.SS",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "公司名称或股票关键词，支持中英文",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stock_history",
            "description": "查询股票历史价格，返回最近若干天的收盘价走势",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码"},
                    "period": {
                        "type": "string",
                        "description": "时间跨度：5d/1mo/3mo/6mo/1y，默认 1mo",
                        "default": "1mo",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "market_overview",
            "description": "查看全球主要股指（上证、深证、恒生、纳斯达克、S&P500、道琼斯）的当前点位和涨跌",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

import threading
import time

_cache: dict = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 60  # 1 minute for price data

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    "Referer": "https://finance.yahoo.com/",
}

_INDICES = [
    ("000001.SS", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("^HSI",      "恒生指数"),
    ("^IXIC",     "纳斯达克"),
    ("^GSPC",     "S&P 500"),
    ("^DJI",      "道琼斯"),
]


def _get_proxies() -> dict | None:
    try:
        from config import config
        proxy = getattr(config, "PROXY", None)
        if proxy:
            return {"http": proxy, "https": proxy}
    except Exception:
        pass
    return None


def _yf_get(url: str, params: dict | None = None) -> dict:
    import requests

    r = requests.get(
        url,
        params=params,
        headers=_HEADERS,
        proxies=_get_proxies(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _chart(symbol: str, interval: str = "1d", range_: str = "1d") -> dict:
    now = time.time()
    key = f"{symbol}:{interval}:{range_}"
    with _cache_lock:
        if key in _cache and now - _cache[key]["t"] < _CACHE_TTL:
            return _cache[key]["data"]

    data = _yf_get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"interval": interval, "range": range_, "includePrePost": "true"},
    )
    with _cache_lock:
        _cache[key] = {"data": data, "t": time.time()}
    return data


def _fmt_large(n: float, currency: str = "") -> str:
    """Format large numbers with CN units (亿/万) or M/B."""
    if currency in ("CNY", "HKD"):
        if abs(n) >= 1e8:
            return f"{n/1e8:.2f}亿"
        if abs(n) >= 1e4:
            return f"{n/1e4:.2f}万"
        return f"{n:.0f}"
    else:
        if abs(n) >= 1e12:
            return f"{n/1e12:.2f}T"
        if abs(n) >= 1e9:
            return f"{n/1e9:.2f}B"
        if abs(n) >= 1e6:
            return f"{n/1e6:.2f}M"
        return f"{n:.0f}"


def _trend(pct: float) -> str:
    if pct > 0:
        return f"🔺 +{pct:.2f}%"
    if pct < 0:
        return f"🔻 {pct:.2f}%"
    return f"➡️ {pct:.2f}%"


def execute(name: str, args: dict) -> dict:
    # ── get_stock_price ──────────────────────────────────────────────────────
    if name == "get_stock_price":
        symbol = args["symbol"].strip().upper()
        details = bool(args.get("details", False))
        try:
            data = _chart(symbol)
        except Exception as e:
            return {"ok": False, "result": f"获取行情失败: {e}\n提示：A股格式 600519.SS / 000001.SZ，港股 0700.HK"}

        res = data.get("chart", {}).get("result")
        if not res:
            err = data.get("chart", {}).get("error", {})
            return {"ok": False, "result": f"未找到股票: {symbol}  ({err.get('description', 'No data')})"}

        meta = res[0]["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose") or meta.get("regularMarketPreviousClose", price)
        change = price - prev_close
        pct = (change / prev_close * 100) if prev_close else 0.0
        currency = meta.get("currency", "")
        exch = meta.get("exchangeName", "")
        mtype = meta.get("instrumentType", "")

        lines = [
            f"📈 {symbol}  [{exch}]  {mtype}",
            f"💰 {price:.4f} {currency}   {_trend(pct)}  ({change:+.4f})",
            f"📊 日高 {meta.get('regularMarketDayHigh', '-'):.2f}  "
            f"日低 {meta.get('regularMarketDayLow', '-'):.2f}",
            f"📦 成交量 {_fmt_large(meta.get('regularMarketVolume', 0), currency)}",
        ]

        if details:
            mktcap = meta.get("marketCap")
            if mktcap:
                lines.append(f"🏦 市值 {_fmt_large(mktcap, currency)} {currency}")
            wk52h = meta.get("fiftyTwoWeekHigh")
            wk52l = meta.get("fiftyTwoWeekLow")
            if wk52h and wk52l:
                lines.append(f"📅 52周区间  {wk52l:.2f} ~ {wk52h:.2f}")
            avg50 = meta.get("fiftyDayAverage")
            avg200 = meta.get("twoHundredDayAverage")
            if avg50:
                lines.append(f"📉 50日均线 {avg50:.2f}  200日均线 {avg200:.2f}" if avg200 else f"📉 50日均线 {avg50:.2f}")

        return {"ok": True, "result": "\n".join(lines)}

    # ── search_stock ─────────────────────────────────────────────────────────
    if name == "search_stock":
        query = args["query"].strip()
        try:
            data = _yf_get(
                "https://query1.finance.yahoo.com/v1/finance/search",
                params={"q": query, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": "false"},
            )
        except Exception as e:
            return {"ok": False, "result": f"搜索失败: {e}"}

        quotes = data.get("quotes", [])
        if not quotes:
            return {"ok": True, "result": f"未找到与 '{query}' 相关的股票"}

        lines = [f"🔍 搜索 '{query}' 的结果:"]
        for q in quotes[:8]:
            sym = q.get("symbol", "")
            short = q.get("shortname") or q.get("longname") or ""
            exch = q.get("exchDisp") or q.get("exchange") or ""
            qtype = q.get("quoteType", "")
            lines.append(f"  {sym:<16} {short[:30]:<32} [{exch}] {qtype}")

        return {"ok": True, "result": "\n".join(lines)}

    # ── stock_history ────────────────────────────────────────────────────────
    if name == "stock_history":
        symbol = args["symbol"].strip().upper()
        period = args.get("period", "1mo")
        interval = "1wk" if period in ("6mo", "1y") else "1d"
        try:
            data = _chart(symbol, interval=interval, range_=period)
        except Exception as e:
            return {"ok": False, "result": f"获取历史数据失败: {e}"}

        res = data.get("chart", {}).get("result")
        if not res:
            return {"ok": False, "result": f"未找到历史数据: {symbol}"}

        timestamps = res[0].get("timestamp", [])
        closes = res[0]["indicators"]["quote"][0].get("close", [])
        currency = res[0]["meta"].get("currency", "")

        if not timestamps:
            return {"ok": True, "result": "暂无历史数据"}

        import datetime
        rows = []
        for ts, c in zip(timestamps, closes):
            if c is None:
                continue
            dt = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            rows.append((dt, c))

        if not rows:
            return {"ok": True, "result": "暂无有效历史数据"}

        # Mini sparkline using blocks
        prices = [r[1] for r in rows]
        mn, mx = min(prices), max(prices)
        rng = mx - mn or 1
        blocks = " ▁▂▃▄▅▆▇█"

        def spark(p):
            idx = int((p - mn) / rng * 8)
            return blocks[min(idx, 8)]

        sparkline = "".join(spark(p) for p in prices)
        start_p, end_p = prices[0], prices[-1]
        total_chg = (end_p - start_p) / start_p * 100

        lines = [
            f"📊 {symbol} 历史走势（{period}）",
            f"区间：{rows[0][0]} → {rows[-1][0]}",
            f"走势：{sparkline}",
            f"开始 {start_p:.2f}  结束 {end_p:.2f}  区间涨跌 {_trend(total_chg)}",
            f"最高 {mx:.2f}  最低 {mn:.2f}  {currency}",
            "",
            f"{'日期':<12} {'收盘价':>10}",
        ]
        for dt, c in rows[-10:]:   # show last 10
            lines.append(f"{dt:<12} {c:>10.4f}")

        return {"ok": True, "result": "\n".join(lines)}

    # ── market_overview ──────────────────────────────────────────────────────
    if name == "market_overview":
        from concurrent.futures import ThreadPoolExecutor

        def _fetch_index(sym_name):
            sym, label = sym_name
            try:
                data = _chart(sym)
                res = data.get("chart", {}).get("result")
                if not res:
                    return f"  {label:<10} —"
                meta = res[0]["meta"]
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("chartPreviousClose") or meta.get("regularMarketPreviousClose") or price
                pct = (price - prev) / prev * 100 if prev else 0
                return f"  {label:<10} {price:>12,.2f}   {_trend(pct)}"
            except Exception as e:
                return f"  {label:<10} 获取失败 ({e})"

        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(_fetch_index, _INDICES))

        lines = ["🌍 全球主要股指:"] + results
        return {"ok": True, "result": "\n".join(lines)}

    return {"ok": False, "result": f"Unknown tool: {name}"}
