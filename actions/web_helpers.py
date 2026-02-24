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
            params={"q": query},
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


def do_web_search(query: str) -> list[dict]:
    """Search with DDG, fall back to Bing if empty."""
    results = search_ddg(query)
    if not results:
        results = search_bing(query)
    return results


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
