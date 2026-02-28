import re
import threading
import time
from html.parser import HTMLParser
import urllib.parse

import requests

_page_cache: dict[str, tuple[str, float]] = {}
_page_cache_lock = threading.Lock()
_PAGE_CACHE_TTL = 300  # 5 minutes


def search_ddg(query: str) -> list[dict]:
    """DuckDuckGo HTML search. Returns list of {title, url, snippet}."""
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
    except Exception:
        return []

    items: list[dict] = []

    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self._mode = None
            self._buf = ""
            self._cur: dict = {}

        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            if tag == "a" and "result__a" in d.get("class", ""):
                self._mode = "title"
                self._buf = ""
                href = d.get("href", "")
                m = re.search(r"uddg=([^&]+)", href)
                self._cur["url"] = urllib.parse.unquote(m.group(1)) if m else href
            elif "result__snippet" in d.get("class", ""):
                self._mode = "snippet"
                self._buf = ""

        def handle_endtag(self, tag):
            if self._mode == "title" and tag == "a":
                self._cur["title"] = self._buf.strip()
                self._mode = None
            elif self._mode == "snippet" and tag in ("a", "td", "div", "span"):
                self._cur["snippet"] = self._buf.strip()
                if self._cur.get("title") and self._cur.get("url"):
                    items.append(dict(self._cur))
                self._cur = {}
                self._mode = None

        def handle_data(self, data):
            if self._mode:
                self._buf += data

    _P().feed(r.text)
    return items[:8]


def search_bing(query: str) -> list[dict]:
    """Bing search fallback. Returns list of {title, url, snippet}."""
    try:
        resp = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "cc": "cn", "setLang": "zh-cn"},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
            timeout=10,
        )
    except Exception:
        return []

    items: list[dict] = []
    for m in re.finditer(
        r'<h2[^>]*>\s*<a[^>]+href="(https?://[^"&]+)"[^>]*>(.*?)</a>',
        resp.text,
        re.DOTALL,
    ):
        url = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if title and not any(s in url for s in ("bing.com", "microsoft.com", "msn.com")):
            items.append({"title": title, "url": url, "snippet": ""})
    return items[:8]


def _is_cjk(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" for ch in s)


def do_web_search(query: str) -> list[dict]:
    """Search helper with better handling for中文/二次元查询.

    - 中文/日文优先用 Bing（更懂本地语境），DDG 作为兜底
    - 对包含“头像/二次元/动漫”等关键词的查询，自动补充一点语境
    """
    q = (query or "").strip()
    if not q:
        return []

    has_cjk = _is_cjk(q)
    anime_keywords = ("头像", "二次元", "动漫", "立绘", "PFP", "pfp")
    is_anime = any(k.lower() in q.lower() for k in anime_keywords)

    search_query = q
    if has_cjk and is_anime:
        # 为头像/角色类搜索增加一点二次元语境提示
        if "头像" in q:
            search_query = f"{q} 二次元 头像"
        else:
            search_query = f"{q} 二次元 动漫"

    if has_cjk:
        # 中文 / 日文 → 直接用 Bing，DDG 兜底
        results = search_bing(search_query)
        if not results and search_query != q:
            results = search_bing(q)
        if not results:
            results = search_ddg(search_query)
    else:
        # 英文等其他语言：先 DDG，再 Bing
        results = search_ddg(q)
        if not results:
            results = search_bing(q)

    return results or []


def extract_html_text(html: str) -> str:
    """Extract main content from HTML. Uses trafilatura if installed, else tag-stripping."""
    try:
        import trafilatura

        text = trafilatura.extract(
            html, include_comments=False, include_tables=True, no_fallback=False,
        )
        if text and len(text.strip()) > 100:
            return re.sub(r"\n{3,}", "\n\n", text).strip()
    except ImportError:
        pass

    class _T(HTMLParser):
        def __init__(self):
            super().__init__()
            self._skip = False
            self._parts: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "footer", "head", "aside"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "footer", "head", "aside"):
                self._skip = False
            if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr"):
                self._parts.append("\n")

        def handle_data(self, data):
            if not self._skip and data.strip():
                self._parts.append(data)

    p = _T()
    p.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "".join(p._parts)).strip()


def fetch_url_text(url: str) -> str:
    """Fetch a URL and extract its main text content, with a short in-memory cache."""
    now = time.time()
    with _page_cache_lock:
        cached = _page_cache.get(url)
        if cached and now - cached[1] < _PAGE_CACHE_TTL:
            return cached[0]

    for attempt in range(3):
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.encoding = resp.apparent_encoding
            text = extract_html_text(resp.text)
            break
        except Exception:
            time.sleep(1.5 ** attempt)
    else:
        return ""

    with _page_cache_lock:
        _page_cache[url] = (text, time.time())
    return text
