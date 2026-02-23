"""Weather skill — queries wttr.in (no API key needed)."""

META = {
    "name": "weather",
    "version": "1.0.0",
    "description": "天气查询（wttr.in，无需 API Key）",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的天气预报（当前 + 未来几天）",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，中英文均可，如 Beijing、上海、Tokyo",
                    },
                    "days": {
                        "type": "integer",
                        "description": "预报天数 1-3，默认 1",
                        "default": 1,
                    },
                },
                "required": ["city"],
            },
        },
    }
]

_ICONS = {
    "sunny": "☀️", "clear": "☀️", "cloud": "☁️", "overcast": "🌥️",
    "rain": "🌧️", "drizzle": "🌦️", "snow": "❄️", "thunder": "⛈️",
    "fog": "🌫️", "mist": "🌫️", "blizzard": "🌨️", "sleet": "🌨️",
    "haze": "🌫️", "wind": "🌬️",
}


def _icon(desc: str) -> str:
    desc_l = desc.lower()
    for kw, em in _ICONS.items():
        if kw in desc_l:
            return em
    return "🌤️"


def execute(name: str, args: dict) -> dict:
    if name != "get_weather":
        return {"ok": False, "result": f"Unknown tool: {name}"}

    import requests
    from urllib.parse import quote

    city = args["city"]
    days = max(1, min(int(args.get("days", 1)), 3))

    try:
        r = requests.get(
            f"https://wttr.in/{quote(city)}?format=j1",
            headers={"User-Agent": "curl/8.0"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {"ok": False, "result": f"获取天气失败: {e}"}

    cur = data["current_condition"][0]
    desc = cur["weatherDesc"][0]["value"]
    temp_c = cur["temp_C"]
    feels_c = cur["FeelsLikeC"]
    humidity = cur["humidity"]
    wind_kmph = cur["windspeedKmph"]
    uv = cur.get("uvIndex", "N/A")
    visibility = cur.get("visibility", "N/A")

    lines = [
        f"📍 {city} 当前天气  {_icon(desc)}",
        f"🌡️  气温 {temp_c}°C（体感 {feels_c}°C）",
        f"☁️  {desc}",
        f"💧 湿度 {humidity}%  💨 风速 {wind_kmph} km/h",
        f"☀️  UV 指数 {uv}  👁️ 能见度 {visibility} km",
    ]

    if days > 1:
        lines.append("")
    for i, day in enumerate(data["weather"][:days]):
        if i == 0 and days == 1:
            break
        date = day["date"]
        max_t = day["maxtempC"]
        min_t = day["mintempC"]
        noon_desc = day["hourly"][4]["weatherDesc"][0]["value"]
        rain_mm = sum(float(h.get("precipMM", 0)) for h in day["hourly"])
        label = ["今天", "明天", "后天"][i]
        lines.append(
            f"{label}({date}): {_icon(noon_desc)} {noon_desc}，"
            f"{min_t}~{max_t}°C，降水 {rain_mm:.1f} mm"
        )

    return {"ok": True, "result": "\n".join(lines)}
