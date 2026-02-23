"""Currency exchange skill — uses open.er-api.com (no API key, free tier)."""

META = {
    "name": "currency",
    "version": "1.0.0",
    "description": "实时汇率换算（open.er-api.com，无需 API Key，每小时缓存）",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "货币汇率换算，例如 100 USD 转 CNY",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "要换算的金额"},
                    "from_currency": {
                        "type": "string",
                        "description": "源货币代码，如 USD、EUR、CNY、JPY",
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "目标货币代码，如 CNY、JPY、GBP",
                    },
                },
                "required": ["amount", "from_currency", "to_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_exchange_rates",
            "description": "列出某种货币对所有主要货币的今日汇率",
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {"type": "string", "description": "基准货币代码，如 USD、CNY"},
                },
                "required": ["base"],
            },
        },
    },
]

import threading
import time

_cache: dict = {}          # base_currency -> {"rates": {...}, "time": float}
_cache_lock = threading.Lock()
_CACHE_TTL = 3600          # 1 hour

_MAJOR_CURRENCIES = [
    "USD", "EUR", "CNY", "JPY", "GBP", "HKD", "KRW",
    "CAD", "AUD", "SGD", "CHF", "TWD", "INR", "MXN",
]

_CURRENCY_NAMES = {
    "USD": "美元", "EUR": "欧元", "CNY": "人民币", "JPY": "日元",
    "GBP": "英镑", "HKD": "港币", "KRW": "韩元", "CAD": "加元",
    "AUD": "澳元", "SGD": "新加坡元", "CHF": "瑞士法郎", "TWD": "新台币",
    "INR": "印度卢比", "MXN": "墨西哥比索",
}


def _get_rates(base: str) -> dict:
    import requests

    base = base.upper()
    now = time.time()
    with _cache_lock:
        if base in _cache and now - _cache[base]["time"] < _CACHE_TTL:
            return _cache[base]["rates"]

    r = requests.get(
        f"https://open.er-api.com/v6/latest/{base}",
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("result") != "success":
        raise ValueError(data.get("error-type", "API error"))

    rates = data["rates"]
    with _cache_lock:
        _cache[base] = {"rates": rates, "time": time.time()}
    return rates


def _fmt_name(code: str) -> str:
    name = _CURRENCY_NAMES.get(code, "")
    return f"{code}({name})" if name else code


def execute(name: str, args: dict) -> dict:
    if name == "convert_currency":
        try:
            amount = float(args["amount"])
            frm = args["from_currency"].upper().strip()
            to = args["to_currency"].upper().strip()
            rates = _get_rates(frm)
            if to not in rates:
                return {"ok": False, "result": f"不支持货币代码: {to}"}
            rate = rates[to]
            converted = amount * rate
            return {
                "ok": True,
                "result": (
                    f"💱 {amount:,.2f} {_fmt_name(frm)}\n"
                    f"   = {converted:,.4f} {_fmt_name(to)}\n"
                    f"汇率：1 {frm} = {rate:.6f} {to}"
                ),
            }
        except Exception as e:
            return {"ok": False, "result": f"换算失败: {e}"}

    if name == "list_exchange_rates":
        try:
            base = args["base"].upper().strip()
            rates = _get_rates(base)
            lines = [f"💱 1 {_fmt_name(base)} 对主要货币汇率:"]
            for cur in _MAJOR_CURRENCIES:
                if cur != base and cur in rates:
                    lines.append(f"  {_fmt_name(cur):<18} {rates[cur]:.4f}")
            return {"ok": True, "result": "\n".join(lines)}
        except Exception as e:
            return {"ok": False, "result": f"获取汇率失败: {e}"}

    return {"ok": False, "result": f"Unknown tool: {name}"}
