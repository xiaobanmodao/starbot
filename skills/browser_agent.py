"""Browser automation skill — Playwright-based headless/headed browser control.

Enables the AI to reliably automate ANY website (Twitter/X, web forms, news sites...)
without depending on screen coordinates like pyautogui.

Install dependencies (one-time):
    uv add playwright
    uv run playwright install chromium

Usage pattern for Twitter (via bg_task):
    1. browser_open("https://x.com")
    2. browser_wait("input[name='text']")   # wait for login
    3. browser_type("input[name='text']", username)
    4. browser_click("button:has-text('Next')")
    ... etc
"""

META = {
    "name": "browser_agent",
    "version": "1.0.0",
    "description": (
        "Playwright 浏览器自动化：可靠地控制任意网站（Twitter、购物、论坛等），"
        "支持点击、输入、截图、等待元素、获取文本、填表等操作"
    ),
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "打开浏览器并访问指定 URL，返回页面标题",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的 URL"},
                    "headless": {
                        "type": "boolean",
                        "description": "是否无头模式（不显示窗口），默认 false（显示窗口便于调试）",
                        "default": False,
                    },
                    "wait_seconds": {
                        "type": "number",
                        "description": "打开后等待页面加载的秒数，默认 2",
                        "default": 2,
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "在当前浏览器中导航到新 URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "目标 URL"},
                    "wait_seconds": {"type": "number", "description": "等待秒数，默认 2", "default": 2},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": (
                "点击页面上的元素。selector 支持 CSS 选择器或文本匹配，如："
                "'button:has-text(\"登录\")'、'input[name=\"password\"]'、'#submit-btn'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS 选择器或文本选择器"},
                    "timeout_s": {"type": "number", "description": "等待元素出现的超时秒数，默认 10", "default": 10},
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "在指定输入框中输入文字（先清空再输入）",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "输入框的 CSS 选择器"},
                    "text": {"type": "string", "description": "要输入的文字"},
                    "clear_first": {
                        "type": "boolean",
                        "description": "是否先清空原内容，默认 true",
                        "default": True,
                    },
                    "press_enter": {
                        "type": "boolean",
                        "description": "输入完成后是否按回车，默认 false",
                        "default": False,
                    },
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_read",
            "description": "读取页面上指定元素的文字内容，或读取整个页面的文字",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS 选择器，留空则返回整个页面文字",
                        "default": "",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "最多返回的字符数，默认 3000",
                        "default": 3000,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "对当前浏览器页面截图，发送到 Discord 对话（通过 SCREENSHOT_PATH 机制）",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "是否截取完整页面（包含滚动区域），默认 false",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_wait",
            "description": "等待页面上出现指定元素（常用于页面加载完成检测）",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "要等待的 CSS 选择器"},
                    "timeout_s": {"type": "number", "description": "超时秒数，默认 15", "default": 15},
                    "state": {
                        "type": "string",
                        "description": "等待状态：visible（可见）/ attached（存在于DOM）/ hidden（消失），默认 visible",
                        "default": "visible",
                    },
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_scroll",
            "description": "滚动页面（用于加载更多内容）",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "滚动方向：down / up / top / bottom，默认 down",
                        "default": "down",
                    },
                    "amount": {
                        "type": "integer",
                        "description": "滚动像素数（direction=down/up 时有效），默认 800",
                        "default": 800,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_links",
            "description": "获取当前页面上所有链接（href 和显示文字）",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_text": {
                        "type": "string",
                        "description": "只返回链接文字包含此词的链接，留空返回全部",
                        "default": "",
                    },
                    "max_links": {
                        "type": "integer",
                        "description": "最多返回数量，默认 20",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_eval",
            "description": "在页面中执行 JavaScript 并返回结果（高级用法）",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "JavaScript 代码，需 return 返回值，如 'return document.title'",
                    },
                },
                "required": ["script"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_close",
            "description": "关闭浏览器，释放资源",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_status",
            "description": "查看浏览器当前状态（是否打开、当前 URL、页面标题）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

import logging
import time

log = logging.getLogger(__name__)

# Singleton browser state
_pw = None          # Playwright instance
_browser = None     # Browser instance
_page = None        # Current page


def _ensure_playwright():
    """Import and check playwright is installed."""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright 未安装。请运行：\n"
            "  uv add playwright\n"
            "  uv run playwright install chromium"
        )


def _get_page():
    global _pw, _browser, _page
    if _page is None or _browser is None:
        raise RuntimeError("浏览器未打开，请先调用 browser_open(url)")
    return _page


def execute(name: str, args: dict) -> dict:
    global _pw, _browser, _page

    # ── browser_open ──────────────────────────────────────────────────────────
    if name == "browser_open":
        url = args["url"]
        headless = bool(args.get("headless", False))
        wait_s = float(args.get("wait_seconds", 2))

        try:
            sync_playwright = _ensure_playwright()
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}

        # Close existing browser if open
        if _browser:
            try:
                _browser.close()
            except Exception:
                pass
        if _pw:
            try:
                _pw.stop()
            except Exception:
                pass

        try:
            _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = _browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
            )
            _page = ctx.new_page()
            _page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_s > 0:
                time.sleep(wait_s)
            title = _page.title()
            return {"ok": True, "result": f"✅ 浏览器已打开\n标题：{title}\nURL：{_page.url}"}
        except Exception as e:
            return {"ok": False, "result": f"打开浏览器失败: {e}"}

    # ── browser_navigate ──────────────────────────────────────────────────────
    if name == "browser_navigate":
        url = args["url"]
        wait_s = float(args.get("wait_seconds", 2))
        try:
            page = _get_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_s > 0:
                time.sleep(wait_s)
            return {"ok": True, "result": f"✅ 已导航到：{page.url}\n标题：{page.title()}"}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"导航失败: {e}"}

    # ── browser_click ─────────────────────────────────────────────────────────
    if name == "browser_click":
        selector = args["selector"]
        timeout_s = float(args.get("timeout_s", 10)) * 1000  # ms
        try:
            page = _get_page()
            page.click(selector, timeout=timeout_s)
            time.sleep(0.5)
            return {"ok": True, "result": f"✅ 已点击：{selector}"}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"点击失败（{selector}）: {e}"}

    # ── browser_type ──────────────────────────────────────────────────────────
    if name == "browser_type":
        selector = args["selector"]
        text = args["text"]
        clear_first = bool(args.get("clear_first", True))
        press_enter = bool(args.get("press_enter", False))
        try:
            page = _get_page()
            if clear_first:
                page.fill(selector, "")
            page.type(selector, text, delay=30)  # human-like delay
            if press_enter:
                page.press(selector, "Enter")
                time.sleep(0.5)
            return {"ok": True, "result": f"✅ 已输入文字到 {selector}"}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"输入失败: {e}"}

    # ── browser_read ──────────────────────────────────────────────────────────
    if name == "browser_read":
        selector = args.get("selector", "").strip()
        max_chars = int(args.get("max_chars", 3000))
        try:
            page = _get_page()
            if selector:
                try:
                    el = page.query_selector(selector)
                    text = el.inner_text() if el else f"元素 '{selector}' 未找到"
                except Exception as e:
                    text = f"读取失败: {e}"
            else:
                # Full page text via trafilatura or fallback
                html = page.content()
                try:
                    import trafilatura
                    text = trafilatura.extract(html) or page.inner_text("body")
                except Exception:
                    text = page.inner_text("body")
            return {"ok": True, "result": text[:max_chars]}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"读取失败: {e}"}

    # ── browser_screenshot ────────────────────────────────────────────────────
    if name == "browser_screenshot":
        full_page = bool(args.get("full_page", False))
        try:
            page = _get_page()
            from actions.executor import SCREENSHOT_PATH
            page.screenshot(path=SCREENSHOT_PATH, full_page=full_page)
            return {"ok": True, "result": f"✅ 截图已保存：{SCREENSHOT_PATH}"}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"截图失败: {e}"}

    # ── browser_wait ──────────────────────────────────────────────────────────
    if name == "browser_wait":
        selector = args["selector"]
        timeout_s = float(args.get("timeout_s", 15)) * 1000
        state = args.get("state", "visible")
        try:
            page = _get_page()
            page.wait_for_selector(selector, state=state, timeout=timeout_s)
            return {"ok": True, "result": f"✅ 元素已出现：{selector}"}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"等待超时（{selector}）: {e}"}

    # ── browser_scroll ────────────────────────────────────────────────────────
    if name == "browser_scroll":
        direction = args.get("direction", "down").lower()
        amount = int(args.get("amount", 800))
        try:
            page = _get_page()
            if direction == "down":
                page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "top":
                page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            return {"ok": True, "result": f"✅ 已滚动 {direction}"}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"滚动失败: {e}"}

    # ── browser_get_links ─────────────────────────────────────────────────────
    if name == "browser_get_links":
        filter_text = args.get("filter_text", "").lower()
        max_links = int(args.get("max_links", 20))
        try:
            page = _get_page()
            links = page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                    text: a.innerText.trim().slice(0, 80),
                    href: a.href
                })).filter(l => l.text && l.href)
            """)
            if filter_text:
                links = [l for l in links if filter_text in l["text"].lower() or filter_text in l["href"].lower()]
            links = links[:max_links]
            if not links:
                return {"ok": True, "result": "页面上未找到匹配的链接"}
            lines = [f"🔗 找到 {len(links)} 个链接:"]
            for i, l in enumerate(links, 1):
                lines.append(f"  {i:2}. {l['text'][:50]}")
                lines.append(f"      {l['href'][:80]}")
            return {"ok": True, "result": "\n".join(lines)}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"获取链接失败: {e}"}

    # ── browser_eval ──────────────────────────────────────────────────────────
    if name == "browser_eval":
        script = args["script"]
        try:
            page = _get_page()
            result = page.evaluate(f"() => {{ {script} }}")
            return {"ok": True, "result": f"执行结果:\n{str(result)[:2000]}"}
        except RuntimeError as e:
            return {"ok": False, "result": str(e)}
        except Exception as e:
            return {"ok": False, "result": f"JS 执行失败: {e}"}

    # ── browser_close ─────────────────────────────────────────────────────────
    if name == "browser_close":
        try:
            if _browser:
                _browser.close()
            if _pw:
                _pw.stop()
        except Exception as e:
            log.warning("Browser close error: %s", e)
        finally:
            _browser = None
            _page = None
            _pw = None
        return {"ok": True, "result": "✅ 浏览器已关闭"}

    # ── browser_status ────────────────────────────────────────────────────────
    if name == "browser_status":
        if _browser is None or _page is None:
            return {"ok": True, "result": "浏览器未打开"}
        try:
            page = _get_page()
            return {
                "ok": True,
                "result": (
                    f"✅ 浏览器运行中\n"
                    f"  标题：{page.title()}\n"
                    f"  URL：{page.url}"
                ),
            }
        except Exception as e:
            return {"ok": False, "result": f"状态获取失败: {e}"}

    return {"ok": False, "result": f"Unknown tool: {name}"}
