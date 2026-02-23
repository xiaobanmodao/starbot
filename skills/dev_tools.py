"""Developer tools skill — JSON, encoding, hashing, timestamps, colors, diff, regex. Pure Python."""

META = {
    "name": "dev_tools",
    "version": "1.0.0",
    "description": "开发者工具集：JSON格式化、编码解码、哈希、时间戳、颜色转换、文本对比、正则测试",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "format_json",
            "description": "格式化、验证、压缩 JSON 字符串，或提取指定路径的值",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "JSON 字符串"},
                    "action": {
                        "type": "string",
                        "description": "操作：format（格式化）/ minify（压缩）/ validate（验证）/ extract（提取路径），默认 format",
                        "default": "format",
                    },
                    "path": {
                        "type": "string",
                        "description": "提取路径（action=extract 时），如 'data.items[0].name'",
                        "default": "",
                    },
                    "indent": {
                        "type": "integer",
                        "description": "格式化缩进空格数，默认 2",
                        "default": 2,
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "encode_decode",
            "description": (
                "文本编码/解码。支持：base64 / base64url / url（URL encoding）/ "
                "html（HTML entities）/ hex（十六进制）/ unicode_escape"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要处理的文本"},
                    "method": {
                        "type": "string",
                        "description": "编码方法：base64 / base64url / url / html / hex / unicode_escape",
                    },
                    "action": {
                        "type": "string",
                        "description": "encode（编码）或 decode（解码），默认 encode",
                        "default": "encode",
                    },
                },
                "required": ["text", "method"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hash_text",
            "description": "计算文本的哈希值，支持 MD5、SHA1、SHA256、SHA512、SHA3-256",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要计算哈希的文本"},
                    "algorithms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "哈希算法列表，留空返回全部：md5/sha1/sha256/sha512/sha3_256",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文本编码，默认 utf-8",
                        "default": "utf-8",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "timestamp_convert",
            "description": "Unix 时间戳与可读时间互转，支持指定时区",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "string",
                        "description": "时间戳数字（如 1700000000）或时间字符串（如 '2024-01-01 12:00:00'），留空返回当前时间",
                        "default": "",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "时区，如 Asia/Shanghai、UTC、US/Eastern，默认本地时区",
                        "default": "local",
                    },
                    "format": {
                        "type": "string",
                        "description": "输出格式，默认 '%Y-%m-%d %H:%M:%S'",
                        "default": "%Y-%m-%d %H:%M:%S",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "color_convert",
            "description": "颜色值互转：HEX ↔ RGB ↔ HSL，支持颜色名称查询",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "string",
                        "description": "颜色值，如 '#FF5733'、'rgb(255,87,51)'、'hsl(11,100%,60%)'、'red'",
                    },
                },
                "required": ["value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diff_text",
            "description": "对比两段文字，以 unified diff 格式显示差异",
            "parameters": {
                "type": "object",
                "properties": {
                    "text1": {"type": "string", "description": "原始文本"},
                    "text2": {"type": "string", "description": "修改后文本"},
                    "label1": {"type": "string", "description": "原始文本标签，默认 'before'", "default": "before"},
                    "label2": {"type": "string", "description": "修改后文本标签，默认 'after'", "default": "after"},
                    "context": {"type": "integer", "description": "显示上下文行数，默认 3", "default": 3},
                },
                "required": ["text1", "text2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "regex_test",
            "description": "测试正则表达式：列出所有匹配项、分组、替换结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "正则表达式"},
                    "text": {"type": "string", "description": "要匹配的文本"},
                    "flags": {
                        "type": "string",
                        "description": "正则标志：i（忽略大小写）/ m（多行）/ s（点匹配换行），可组合如 'im'",
                        "default": "",
                    },
                    "replace": {
                        "type": "string",
                        "description": "替换字符串（留空则只显示匹配，不替换）",
                        "default": "",
                    },
                },
                "required": ["pattern", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_uuid",
            "description": "生成 UUID（v4 随机）或 ULID，可批量生成",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "生成数量，默认 1，最多 20", "default": 1},
                    "format": {
                        "type": "string",
                        "description": "格式：uuid4 / uuid4_no_dash / upper，默认 uuid4",
                        "default": "uuid4",
                    },
                },
                "required": [],
            },
        },
    },
]

import hashlib
import json
import re


# ── format_json ──────────────────────────────────────────────────────────────

def _json_extract(obj, path: str):
    """Traverse object by dot-notation path, e.g. 'data.items[0].name'."""
    parts = re.split(r'\.|\[(\d+)\]', path)
    cur = obj
    for part in parts:
        if part is None or part == "":
            continue
        if part.isdigit():
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


# ── encode_decode ────────────────────────────────────────────────────────────

def _encode(text: str, method: str) -> str:
    import base64, urllib.parse, html as html_mod
    m = method.lower()
    if m == "base64":
        return base64.b64encode(text.encode()).decode()
    if m == "base64url":
        return base64.urlsafe_b64encode(text.encode()).decode()
    if m == "url":
        return urllib.parse.quote(text, safe="")
    if m == "html":
        return html_mod.escape(text)
    if m == "hex":
        return text.encode().hex()
    if m == "unicode_escape":
        return text.encode("unicode_escape").decode("ascii")
    raise ValueError(f"不支持的编码方法: {method}")


def _decode(text: str, method: str) -> str:
    import base64, urllib.parse, html as html_mod
    m = method.lower()
    if m == "base64":
        return base64.b64decode(text.encode()).decode("utf-8", errors="replace")
    if m == "base64url":
        return base64.urlsafe_b64decode(text.encode() + b"==").decode("utf-8", errors="replace")
    if m == "url":
        return urllib.parse.unquote(text)
    if m == "html":
        return html_mod.unescape(text)
    if m == "hex":
        return bytes.fromhex(text).decode("utf-8", errors="replace")
    if m == "unicode_escape":
        return text.encode("ascii").decode("unicode_escape")
    raise ValueError(f"不支持的编码方法: {method}")


# ── color_convert ────────────────────────────────────────────────────────────

_COLOR_NAMES = {
    "red": (255, 0, 0), "green": (0, 128, 0), "blue": (0, 0, 255),
    "white": (255, 255, 255), "black": (0, 0, 0), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255), "orange": (255, 165, 0),
    "purple": (128, 0, 128), "pink": (255, 192, 203), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "silver": (192, 192, 192), "gold": (255, 215, 0),
    "brown": (165, 42, 42), "lime": (0, 255, 0), "navy": (0, 0, 128),
    "teal": (0, 128, 128), "maroon": (128, 0, 0), "olive": (128, 128, 0),
    "coral": (255, 127, 80), "salmon": (250, 128, 114), "khaki": (240, 230, 140),
    "indigo": (75, 0, 130), "violet": (238, 130, 238), "crimson": (220, 20, 60),
}


def _parse_color(value: str):
    """Parse any color format to (r, g, b)."""
    v = value.strip()

    # Named color
    if v.lower() in _COLOR_NAMES:
        return _COLOR_NAMES[v.lower()]

    # HEX
    hex_match = re.match(r"#?([0-9a-fA-F]{6})$", v)
    if hex_match:
        h = hex_match.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    # Short HEX
    short_hex = re.match(r"#?([0-9a-fA-F]{3})$", v)
    if short_hex:
        h = short_hex.group(1)
        return int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16)

    # RGB
    rgb = re.match(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", v, re.IGNORECASE)
    if rgb:
        return int(rgb.group(1)), int(rgb.group(2)), int(rgb.group(3))

    # HSL
    hsl = re.match(r"hsl\s*\(\s*(\d+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)", v, re.IGNORECASE)
    if hsl:
        h, s, l = float(hsl.group(1)), float(hsl.group(2)) / 100, float(hsl.group(3)) / 100
        return _hsl_to_rgb(h, s, l)

    raise ValueError(f"无法识别的颜色格式: {value}")


def _hsl_to_rgb(h, s, l):
    if s == 0:
        v = int(l * 255)
        return v, v, v
    def hue_to_rgb(p, q, t):
        t = t % 1
        if t < 1/6: return p + (q - p) * 6 * t
        if t < 1/2: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6
        return p
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    h /= 360
    r = int(hue_to_rgb(p, q, h + 1/3) * 255)
    g = int(hue_to_rgb(p, q, h) * 255)
    b = int(hue_to_rgb(p, q, h - 1/3) * 255)
    return r, g, b


def _rgb_to_hsl(r, g, b):
    r, g, b = r/255, g/255, b/255
    mn, mx = min(r, g, b), max(r, g, b)
    l = (mn + mx) / 2
    if mn == mx:
        return 0.0, 0.0, round(l * 100, 1)
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h = round(h * 60, 1)
    return h, round(s * 100, 1), round(l * 100, 1)


# ── Main execute ─────────────────────────────────────────────────────────────

def execute(name: str, args: dict) -> dict:

    if name == "format_json":
        text = args["text"].strip()
        action = args.get("action", "format").lower()
        indent = int(args.get("indent", 2))
        path = args.get("path", "")

        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            return {"ok": False, "result": f"JSON 解析错误: {e}"}

        if action == "validate":
            kind = type(obj).__name__
            size = len(text)
            if isinstance(obj, (dict, list)):
                count = len(obj)
                return {"ok": True, "result": f"✅ 合法 JSON\n类型：{kind}，包含 {count} 个元素，大小 {size} 字节"}
            return {"ok": True, "result": f"✅ 合法 JSON，类型：{kind}，大小 {size} 字节"}

        if action == "minify":
            result = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            return {"ok": True, "result": f"压缩后（{len(result)} 字节）:\n{result[:3000]}"}

        if action == "extract":
            if not path:
                return {"ok": False, "result": "提取路径 (path) 不能为空"}
            try:
                extracted = _json_extract(obj, path)
                pretty = json.dumps(extracted, ensure_ascii=False, indent=2)
                return {"ok": True, "result": f"路径 '{path}' 的值:\n{pretty[:3000]}"}
            except (KeyError, IndexError, TypeError) as e:
                return {"ok": False, "result": f"路径不存在: {e}"}

        # Default: format
        result = json.dumps(obj, ensure_ascii=False, indent=indent)
        return {"ok": True, "result": result[:5000]}

    if name == "encode_decode":
        text = args["text"]
        method = args["method"].lower()
        action = args.get("action", "encode").lower()
        try:
            if action == "encode":
                result = _encode(text, method)
            else:
                result = _decode(text, method)
        except Exception as e:
            return {"ok": False, "result": f"{action} 失败: {e}"}
        return {"ok": True, "result": f"{'编码' if action == 'encode' else '解码'}结果（{method}）:\n{result}"}

    if name == "hash_text":
        text = args["text"]
        algorithms = args.get("algorithms") or ["md5", "sha1", "sha256", "sha512", "sha3_256"]
        encoding = args.get("encoding", "utf-8")

        try:
            data = text.encode(encoding)
        except LookupError:
            return {"ok": False, "result": f"不支持的编码: {encoding}"}

        algo_map = {
            "md5": hashlib.md5, "sha1": hashlib.sha1,
            "sha256": hashlib.sha256, "sha512": hashlib.sha512,
            "sha3_256": hashlib.sha3_256, "sha3_512": hashlib.sha3_512,
            "sha224": hashlib.sha224, "blake2b": hashlib.blake2b,
        }
        lines = [f"🔒 哈希计算（{len(data)} 字节）"]
        for algo in algorithms:
            fn = algo_map.get(algo.lower().replace("-", "_"))
            if fn is None:
                lines.append(f"  {algo}: 不支持的算法")
            else:
                h = fn(data).hexdigest()
                lines.append(f"  {algo.upper():<12}: {h}")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "timestamp_convert":
        import datetime

        value = str(args.get("value", "") or "").strip()
        tz_name = args.get("timezone", "local")
        fmt = args.get("format", "%Y-%m-%d %H:%M:%S")

        # Resolve timezone
        tz = None
        if tz_name and tz_name.lower() not in ("local", ""):
            try:
                import zoneinfo
                tz = zoneinfo.ZoneInfo(tz_name)
            except Exception:
                return {"ok": False, "result": f"未知时区: {tz_name}"}

        now_ts = datetime.datetime.now(tz=tz)
        now_utc = datetime.datetime.utcnow()

        if not value:
            lines = [
                "🕒 当前时间",
                f"  本地：{now_ts.strftime(fmt)}",
                f"  UTC ：{now_utc.strftime(fmt)}",
                f"  Unix：{int(now_ts.timestamp())}",
                f"  毫秒：{int(now_ts.timestamp() * 1000)}",
            ]
            return {"ok": True, "result": "\n".join(lines)}

        # Try as Unix timestamp
        if re.match(r"^\d{10,13}$", value):
            ts = int(value)
            if len(value) == 13:
                ts //= 1000  # milliseconds
            dt_local = datetime.datetime.fromtimestamp(ts, tz=tz)
            dt_utc = datetime.datetime.utcfromtimestamp(ts)
            lines = [
                f"🕒 时间戳转换：{value}",
                f"  本地（{tz_name}）：{dt_local.strftime(fmt)}",
                f"  UTC：{dt_utc.strftime(fmt)}",
                f"  Unix（秒）：{ts}",
                f"  Unix（毫秒）：{ts * 1000}",
            ]
            return {"ok": True, "result": "\n".join(lines)}

        # Try as datetime string
        for f_try in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S",
                      "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(value, f_try)
                if tz:
                    dt = dt.replace(tzinfo=tz)
                ts = int(dt.timestamp())
                lines = [
                    f"🕒 时间字符串转换：{value}",
                    f"  Unix（秒）：{ts}",
                    f"  Unix（毫秒）：{ts * 1000}",
                    f"  格式化：{dt.strftime(fmt)}",
                ]
                return {"ok": True, "result": "\n".join(lines)}
            except ValueError:
                continue

        return {"ok": False, "result": f"无法解析时间值: '{value}'，请输入 Unix 时间戳或 'YYYY-MM-DD HH:MM:SS' 格式"}

    if name == "color_convert":
        value = args["value"].strip()
        try:
            r, g, b = _parse_color(value)
        except ValueError as e:
            return {"ok": False, "result": str(e)}

        r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
        h, s, l = _rgb_to_hsl(r, g, b)
        hex_val = f"#{r:02X}{g:02X}{b:02X}"

        # Color block simulation with Unicode
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        block = "██████"

        lines = [
            f"🎨 颜色：{value}",
            f"  HEX：{hex_val}",
            f"  RGB：rgb({r}, {g}, {b})",
            f"  HSL：hsl({h:.0f}, {s:.1f}%, {l:.1f}%)",
            f"  亮度：{brightness:.0f}/255  ({'深色' if brightness < 128 else '浅色'}背景适合{'白' if brightness < 128 else '黑'}字)",
        ]
        return {"ok": True, "result": "\n".join(lines)}

    if name == "diff_text":
        import difflib
        text1 = args["text1"]
        text2 = args["text2"]
        label1 = args.get("label1", "before")
        label2 = args.get("label2", "after")
        context = int(args.get("context", 3))

        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            lines1, lines2,
            fromfile=label1, tofile=label2,
            n=context,
        ))

        if not diff:
            return {"ok": True, "result": "✅ 两段文字完全相同，无差异"}

        # Count stats
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

        diff_str = "".join(diff)[:4000]
        return {
            "ok": True,
            "result": (
                f"📝 文本差异：+{added} 行，-{removed} 行\n"
                f"{'─'*50}\n"
                f"{diff_str}"
            ),
        }

    if name == "regex_test":
        pattern = args["pattern"]
        text = args["text"]
        flags_str = args.get("flags", "").lower()
        replace = args.get("replace", "")

        flag_val = 0
        if "i" in flags_str:
            flag_val |= re.IGNORECASE
        if "m" in flags_str:
            flag_val |= re.MULTILINE
        if "s" in flags_str:
            flag_val |= re.DOTALL

        try:
            compiled = re.compile(pattern, flag_val)
        except re.error as e:
            return {"ok": False, "result": f"正则表达式错误: {e}"}

        matches = list(compiled.finditer(text))
        lines = [
            f"🔍 正则测试：/{pattern}/{'i' if flag_val & re.IGNORECASE else ''}{'m' if flag_val & re.MULTILINE else ''}",
            f"共匹配 {len(matches)} 处",
        ]

        if matches:
            lines.append("")
            for i, m in enumerate(matches[:20], 1):
                lines.append(f"匹配 {i}: [{m.start()}:{m.end()}]  →  '{m.group()[:60]}'")
                if m.groups():
                    for j, g in enumerate(m.groups(), 1):
                        lines.append(f"  分组 {j}: '{g}'")
            if len(matches) > 20:
                lines.append(f"…（仅显示前 20 个）")

        if replace:
            try:
                result = compiled.sub(replace, text)
                lines += ["", f"🔄 替换结果（将匹配内容替换为 '{replace}'）:", result[:2000]]
            except re.error as e:
                lines.append(f"替换失败: {e}")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "generate_uuid":
        import uuid
        count = min(int(args.get("count", 1)), 20)
        fmt = args.get("format", "uuid4").lower()
        uuids = []
        for _ in range(count):
            u = uuid.uuid4()
            if fmt == "uuid4_no_dash":
                uuids.append(str(u).replace("-", ""))
            elif fmt == "upper":
                uuids.append(str(u).upper())
            else:
                uuids.append(str(u))

        return {
            "ok": True,
            "result": f"🆔 生成 {count} 个 UUID（{fmt}）:\n" + "\n".join(uuids),
        }

    return {"ok": False, "result": f"Unknown tool: {name}"}
