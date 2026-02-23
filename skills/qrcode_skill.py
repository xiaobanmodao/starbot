"""QR code generator skill — saves PNG to Desktop."""

META = {
    "name": "qrcode_skill",
    "version": "1.0.0",
    "description": "生成 QR 二维码图片，保存到桌面（需要 qrcode[pil] 库）",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_qr",
            "description": (
                "将任意文字/URL/WiFi 信息编码为 QR 二维码图片，"
                "保存到桌面并返回文件路径。"
                "WiFi 格式示例：WIFI:S:<SSID>;T:WPA;P:<密码>;;"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要编码的内容，如 URL、纯文字、WiFi 字符串等",
                    },
                    "filename": {
                        "type": "string",
                        "description": "保存的文件名（不含路径），默认 qr.png",
                    },
                    "error_correction": {
                        "type": "string",
                        "description": "纠错级别 L/M/Q/H，越高容错越强但密度越大，默认 M",
                        "default": "M",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_wifi_qr",
            "description": "快捷生成 WiFi 连接二维码，扫码即可连接 WiFi",
            "parameters": {
                "type": "object",
                "properties": {
                    "ssid": {"type": "string", "description": "WiFi 名称（SSID）"},
                    "password": {"type": "string", "description": "WiFi 密码"},
                    "security": {
                        "type": "string",
                        "description": "加密类型：WPA / WEP / nopass，默认 WPA",
                        "default": "WPA",
                    },
                },
                "required": ["ssid", "password"],
            },
        },
    },
]

_EC_MAP = {"L": None, "M": None, "Q": None, "H": None}  # filled lazily


def _get_ec(level: str):
    try:
        import qrcode.constants as c
        return {
            "L": c.ERROR_CORRECT_L,
            "M": c.ERROR_CORRECT_M,
            "Q": c.ERROR_CORRECT_Q,
            "H": c.ERROR_CORRECT_H,
        }.get(level.upper(), c.ERROR_CORRECT_M)
    except ImportError:
        return None


def _make_qr(content: str, filename: str, ec_level: str = "M") -> dict:
    try:
        import qrcode
    except ImportError:
        return {
            "ok": False,
            "result": (
                "缺少依赖，请运行：\n"
                "  uv add qrcode[pil]\n"
                "或：pip install qrcode[pil]"
            ),
        }

    import os

    ec = _get_ec(ec_level)
    if not filename.lower().endswith(".png"):
        filename += ".png"

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    out_path = os.path.join(desktop, filename)

    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=ec,
            box_size=10,
            border=4,
        )
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(out_path)
    except Exception as e:
        return {"ok": False, "result": f"生成失败: {e}"}

    preview = content[:80] + ("…" if len(content) > 80 else "")
    return {
        "ok": True,
        "result": f"✅ 二维码已保存到桌面：{filename}\n内容：{preview}",
    }


def execute(name: str, args: dict) -> dict:
    if name == "generate_qr":
        return _make_qr(
            content=args["content"],
            filename=args.get("filename", "qr.png"),
            ec_level=args.get("error_correction", "M"),
        )

    if name == "generate_wifi_qr":
        ssid = args["ssid"]
        password = args["password"]
        security = args.get("security", "WPA").upper()
        # Escape special characters in WiFi QR format
        def _esc(s):
            for ch in r'\;,"':
                s = s.replace(ch, "\\" + ch)
            return s
        wifi_str = f"WIFI:S:{_esc(ssid)};T:{security};P:{_esc(password)};;"
        safe_name = "".join(c if c.isalnum() else "_" for c in ssid) + "_wifi.png"
        return _make_qr(content=wifi_str, filename=safe_name, ec_level="M")

    return {"ok": False, "result": f"Unknown tool: {name}"}
