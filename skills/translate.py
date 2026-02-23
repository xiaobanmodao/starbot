"""Translation skill — MyMemory free API (no key, 5000 chars/day), with LibreTranslate fallback."""

META = {
    "name": "translate",
    "version": "1.0.0",
    "description": "多语言翻译与语言检测（MyMemory 免费 API，无需注册，支持 50+ 种语言）",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "translate",
            "description": (
                "将文字翻译到目标语言。支持中英日韩法德西俄等 50+ 种语言。"
                "语言代码：zh-CN（简中）/ en（英语）/ ja（日语）/ ko（韩语）/ "
                "fr（法语）/ de（德语）/ es（西班牙语）/ ru（俄语）/ ar（阿拉伯语）"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要翻译的文字"},
                    "to": {
                        "type": "string",
                        "description": "目标语言代码，如 en、zh-CN、ja、ko、fr",
                    },
                    "from_lang": {
                        "type": "string",
                        "description": "源语言代码，默认 auto（自动检测）",
                        "default": "auto",
                    },
                },
                "required": ["text", "to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_language",
            "description": "检测一段文字是什么语言，返回语言代码和置信度",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要检测语言的文字"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "batch_translate",
            "description": "批量翻译多条文字到同一目标语言，一次调用返回所有结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要翻译的文字列表（最多 10 条）",
                    },
                    "to": {"type": "string", "description": "目标语言代码"},
                    "from_lang": {
                        "type": "string",
                        "description": "源语言，默认 auto",
                        "default": "auto",
                    },
                },
                "required": ["texts", "to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_languages",
            "description": "列出所有支持的语言代码和名称",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

_LANG_NAMES = {
    "af": "南非荷兰语", "sq": "阿尔巴尼亚语", "am": "阿姆哈拉语",
    "ar": "阿拉伯语", "hy": "亚美尼亚语", "az": "阿塞拜疆语",
    "eu": "巴斯克语", "be": "白俄罗斯语", "bn": "孟加拉语",
    "bs": "波斯尼亚语", "bg": "保加利亚语", "ca": "加泰罗尼亚语",
    "ceb": "宿务语", "zh-CN": "中文（简体）", "zh-TW": "中文（繁体）",
    "co": "科西嘉语", "hr": "克罗地亚语", "cs": "捷克语", "da": "丹麦语",
    "nl": "荷兰语", "en": "英语", "eo": "世界语", "et": "爱沙尼亚语",
    "fi": "芬兰语", "fr": "法语", "fy": "弗里西语", "gl": "加利西亚语",
    "ka": "格鲁吉亚语", "de": "德语", "el": "希腊语", "gu": "古吉拉特语",
    "ht": "海地克里奥尔语", "ha": "豪萨语", "haw": "夏威夷语",
    "he": "希伯来语", "hi": "印地语", "hmn": "苗语", "hu": "匈牙利语",
    "is": "冰岛语", "ig": "伊博语", "id": "印度尼西亚语", "ga": "爱尔兰语",
    "it": "意大利语", "ja": "日语", "jv": "爪哇语", "kn": "卡纳达语",
    "kk": "哈萨克语", "km": "高棉语", "rw": "卢旺达语", "ko": "韩语",
    "ku": "库尔德语", "ky": "吉尔吉斯语", "lo": "老挝语", "lv": "拉脱维亚语",
    "lt": "立陶宛语", "lb": "卢森堡语", "mk": "马其顿语", "mg": "马尔加什语",
    "ms": "马来语", "ml": "马拉雅拉姆语", "mt": "马耳他语", "mi": "毛利语",
    "mr": "马拉地语", "mn": "蒙古语", "my": "缅甸语", "ne": "尼泊尔语",
    "no": "挪威语", "ny": "尼扬贾语", "or": "奥利亚语", "ps": "普什图语",
    "fa": "波斯语", "pl": "波兰语", "pt": "葡萄牙语", "pa": "旁遮普语",
    "ro": "罗马尼亚语", "ru": "俄语", "sm": "萨摩亚语", "gd": "苏格兰盖尔语",
    "sr": "塞尔维亚语", "st": "塞索托语", "sn": "修纳语", "sd": "信德语",
    "si": "僧伽罗语", "sk": "斯洛伐克语", "sl": "斯洛文尼亚语", "so": "索马里语",
    "es": "西班牙语", "su": "巽他语", "sw": "斯瓦希里语", "sv": "瑞典语",
    "tl": "菲律宾语", "tg": "塔吉克语", "ta": "泰米尔语", "tt": "鞑靼语",
    "te": "泰卢固语", "th": "泰语", "tr": "土耳其语", "tk": "土库曼语",
    "uk": "乌克兰语", "ur": "乌尔都语", "ug": "维吾尔语", "uz": "乌兹别克语",
    "vi": "越南语", "cy": "威尔士语", "xh": "科萨语", "yi": "意第绪语",
    "yo": "约鲁巴语", "zu": "祖鲁语",
}


def _mymemory_translate(text: str, to_lang: str, from_lang: str = "auto") -> dict:
    """Call MyMemory API. Returns {translated, detected_lang, match}."""
    import requests

    # MyMemory uses | separator for langpair
    if from_lang == "auto":
        # Let MyMemory auto-detect by using empty source
        langpair = f"|{to_lang}"
    else:
        langpair = f"{from_lang}|{to_lang}"

    r = requests.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text[:500], "langpair": langpair},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("responseStatus") != 200:
        raise ValueError(data.get("responseDetails", "API error"))

    match = data["responseData"]
    return {
        "translated": match.get("translatedText", ""),
        "match": match.get("match", 0),
        "detected": data.get("detectedLanguage", {}).get("language", ""),
    }


def _lang_name(code: str) -> str:
    return _LANG_NAMES.get(code, code)


def execute(name: str, args: dict) -> dict:

    if name == "translate":
        text = args["text"].strip()
        to_lang = args["to"].strip()
        from_lang = args.get("from_lang", "auto").strip()

        if not text:
            return {"ok": False, "result": "文本不能为空"}
        if len(text) > 500:
            return {"ok": False, "result": "文本过长，单次翻译最多 500 字符（可拆分多次调用）"}

        try:
            res = _mymemory_translate(text, to_lang, from_lang)
        except Exception as e:
            return {"ok": False, "result": f"翻译失败: {e}"}

        translated = res["translated"]
        detected = res.get("detected", "")
        quality = int(res.get("match", 0) * 100)

        lines = [
            f"🌐 翻译结果（→ {_lang_name(to_lang)}）",
        ]
        if detected and from_lang == "auto":
            lines.append(f"   检测到源语言：{_lang_name(detected)} ({detected})")
        lines += ["", translated]
        if quality < 60:
            lines.append(f"\n⚠️ 翻译置信度较低（{quality}%），建议核实")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "detect_language":
        text = args["text"][:300].strip()
        if not text:
            return {"ok": False, "result": "文本不能为空"}

        # Use MyMemory to detect by translating a tiny bit
        try:
            import requests
            r = requests.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text[:50], "langpair": "|en"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            detected = data.get("detectedLanguage", {})
            code = detected.get("language", "")
            confidence = detected.get("confidence", 0)
        except Exception as e:
            return {"ok": False, "result": f"语言检测失败: {e}"}

        if not code:
            return {"ok": True, "result": "无法确定语言（可能是混合语言或过短）"}

        name_cn = _lang_name(code)
        conf_pct = int(float(confidence) * 100) if confidence else 0
        return {
            "ok": True,
            "result": (
                f"🔍 语言检测结果\n"
                f"   语言：{name_cn}（{code}）\n"
                f"   置信度：{conf_pct}%"
            ),
        }

    if name == "batch_translate":
        texts = args.get("texts", [])[:10]
        to_lang = args["to"].strip()
        from_lang = args.get("from_lang", "auto").strip()

        if not texts:
            return {"ok": False, "result": "文字列表不能为空"}

        from concurrent.futures import ThreadPoolExecutor
        import time as _time

        def _do(text):
            try:
                res = _mymemory_translate(text[:500], to_lang, from_lang)
                _time.sleep(0.3)  # rate limit
                return res["translated"]
            except Exception as e:
                return f"[翻译失败: {e}]"

        with ThreadPoolExecutor(max_workers=3) as ex:
            translated = list(ex.map(_do, texts))

        lines = [f"🌐 批量翻译（→ {_lang_name(to_lang)}，共 {len(texts)} 条）", ""]
        for i, (orig, trans) in enumerate(zip(texts, translated), 1):
            lines.append(f"{i}. 原文：{orig[:60]}")
            lines.append(f"   译文：{trans}")
            lines.append("")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "list_languages":
        lines = ["🌐 支持的语言列表:", ""]
        common = ["zh-CN", "en", "ja", "ko", "fr", "de", "es", "ru",
                  "ar", "pt", "it", "nl", "pl", "vi", "th", "tr",
                  "fa", "hi", "id", "ms"]
        lines.append("【常用语言】")
        for code in common:
            lines.append(f"  {code:<10} {_LANG_NAMES.get(code, code)}")
        lines.append("\n【全部语言（代码）】")
        others = sorted(k for k in _LANG_NAMES if k not in common)
        row = []
        for code in others:
            row.append(f"{code}={_LANG_NAMES[code]}")
            if len(row) == 3:
                lines.append("  " + "  ".join(f"{r:<25}" for r in row))
                row = []
        if row:
            lines.append("  " + "  ".join(f"{r:<25}" for r in row))
        return {"ok": True, "result": "\n".join(lines)}

    return {"ok": False, "result": f"Unknown tool: {name}"}
