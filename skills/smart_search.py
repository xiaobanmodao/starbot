"""High-efficiency search skill — Wikipedia, table extraction, site crawling, multi-source aggregation."""

META = {
    "name": "smart_search",
    "version": "1.0.0",
    "description": "高效信息查询：Wikipedia 精准搜索、网页表格提取、站点爬虫、多源聚合研究",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "wiki_lookup",
            "description": (
                "在 Wikipedia 上搜索并返回词条的完整摘要。"
                "适合查询百科知识、历史事件、人物介绍、科学概念等。"
                "支持中英文，自动选择对应语言版本"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要查询的词条或关键词"},
                    "lang": {
                        "type": "string",
                        "description": "语言版本：zh（中文）/ en（英文）/ ja（日文）等，默认 zh",
                        "default": "zh",
                    },
                    "full": {
                        "type": "boolean",
                        "description": "是否返回完整内容（更长），默认 false 只返回摘要",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_table",
            "description": (
                "从指定网页 URL 提取所有 HTML 表格，以文字形式返回。"
                "适合查询股票数据、排行榜、统计数据、对比表格等"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "包含表格的网页 URL"},
                    "table_index": {
                        "type": "integer",
                        "description": "要提取的表格索引（从 0 开始），-1 表示提取所有，默认 0",
                        "default": 0,
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "每张表最多显示行数，默认 30",
                        "default": 30,
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crawl_site",
            "description": (
                "在指定网站内爬取多个页面，搜索包含关键词的内容。"
                "适合在文档站、新闻站、论坛中深度挖掘信息"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_url": {"type": "string", "description": "起始 URL"},
                    "keyword": {"type": "string", "description": "要搜索的关键词"},
                    "max_pages": {
                        "type": "integer",
                        "description": "最多爬取页面数，默认 10，最大 30",
                        "default": 10,
                    },
                    "same_domain": {
                        "type": "boolean",
                        "description": "是否只爬取同域名页面，默认 true",
                        "default": True,
                    },
                },
                "required": ["start_url", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_sources",
            "description": (
                "并行访问多个 URL，提取各页面主要内容后汇总比较，"
                "适合横向对比不同来源对同一主题的观点"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要对比的 URL 列表（2-6 个）",
                    },
                    "focus": {
                        "type": "string",
                        "description": "重点关注的问题或角度",
                        "default": "",
                    },
                },
                "required": ["urls"],
            },
        },
    },
]

import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, quote

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _get_proxies():
    try:
        from config import config
        proxy = getattr(config, "PROXY", None)
        if proxy:
            return {"http": proxy, "https": proxy}
    except Exception:
        pass
    return None


def _fetch(url: str, timeout: int = 10) -> str:
    import requests
    r = requests.get(url, headers=_HEADERS, proxies=_get_proxies(), timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def _extract_text(html: str, max_chars: int = 6000) -> str:
    """Extract clean text from HTML using trafilatura with fallback."""
    try:
        import trafilatura
        text = trafilatura.extract(html, include_links=False, include_images=False)
        if text and len(text) > 100:
            return text[:max_chars]
    except Exception:
        pass

    # Fallback: strip tags
    class _Strip(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "header", "footer"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "header", "footer"):
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                stripped = data.strip()
                if stripped:
                    self.parts.append(stripped)

    p = _Strip()
    p.feed(html)
    return " ".join(p.parts)[:max_chars]


# ── wiki_lookup ─────────────────────────────────────────────────────────────

def _wiki_summary(query: str, lang: str) -> dict:
    import requests
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(query)}"
    r = requests.get(url, headers=_HEADERS, proxies=_get_proxies(), timeout=10)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


def _wiki_search(query: str, lang: str, limit: int = 5) -> list[dict]:
    import requests
    r = requests.get(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "query", "list": "search",
            "srsearch": query, "format": "json", "srlimit": limit,
        },
        headers=_HEADERS,
        proxies=_get_proxies(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("query", {}).get("search", [])


def _wiki_full(title: str, lang: str, max_chars: int = 6000) -> str:
    import requests
    r = requests.get(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "query", "titles": title, "prop": "extracts",
            "explaintext": "true", "exsectionformat": "plain",
            "format": "json",
        },
        headers=_HEADERS,
        proxies=_get_proxies(),
        timeout=10,
    )
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        return page.get("extract", "")[:max_chars]
    return ""


# ── scrape_table ─────────────────────────────────────────────────────────────

class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = 0
        self._in_row = False
        self._in_cell = False
        self._cur_table: list[list[str]] = []
        self._cur_row: list[str] = []
        self._cur_cell: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table += 1
            if self._in_table == 1:
                self._cur_table = []
        elif self._in_table == 1:
            if tag == "tr":
                self._in_row = True
                self._cur_row = []
            elif tag in ("td", "th") and self._in_row:
                self._in_cell = True
                self._cur_cell = []

    def handle_endtag(self, tag):
        if tag == "table":
            if self._in_table == 1 and self._cur_table:
                self.tables.append(self._cur_table)
            self._in_table = max(0, self._in_table - 1)
        elif self._in_table == 1:
            if tag in ("td", "th") and self._in_cell:
                self._cur_row.append(" ".join(self._cur_cell).strip())
                self._in_cell = False
            elif tag == "tr" and self._in_row:
                if self._cur_row:
                    self._cur_table.append(self._cur_row)
                self._in_row = False

    def handle_data(self, data):
        if self._in_cell:
            t = data.strip()
            if t:
                self._cur_cell.append(t)


def _render_table(rows: list[list[str]], max_rows: int = 30) -> str:
    if not rows:
        return "(空表)"
    # Compute column widths
    n_cols = max(len(r) for r in rows)
    widths = [0] * n_cols
    for row in rows[:max_rows]:
        for i, cell in enumerate(row):
            if i < n_cols:
                widths[i] = min(max(widths[i], len(cell)), 30)

    def fmt_row(row):
        cells = []
        for i in range(n_cols):
            cell = row[i] if i < len(row) else ""
            cells.append(cell[:widths[i]].ljust(widths[i]))
        return " | ".join(cells)

    sep = "-+-".join("-" * w for w in widths)
    lines = [fmt_row(rows[0]), sep]
    for row in rows[1:max_rows]:
        lines.append(fmt_row(row))
    if len(rows) > max_rows:
        lines.append(f"…（共 {len(rows)} 行，仅显示前 {max_rows} 行）")
    return "\n".join(lines)


# ── crawl_site ──────────────────────────────────────────────────────────────

def _crawl(start_url: str, keyword: str, max_pages: int, same_domain: bool) -> list[dict]:
    from collections import deque
    import requests

    domain = urlparse(start_url).netloc
    visited: set[str] = set()
    queue: deque[str] = deque([start_url])
    hits: list[dict] = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        try:
            r = requests.get(url, headers=_HEADERS, proxies=_get_proxies(), timeout=8)
            html = r.text
        except Exception:
            continue

        text = _extract_text(html, max_chars=3000)
        if keyword.lower() in text.lower():
            snippet_idx = text.lower().find(keyword.lower())
            start = max(0, snippet_idx - 100)
            snippet = text[start:snippet_idx + 200].replace("\n", " ").strip()
            hits.append({"url": url, "snippet": snippet})

        # Extract links
        for href in re.findall(r'href=["\']([^"\']+)["\']', html):
            abs_url = urljoin(url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme not in ("http", "https"):
                continue
            if same_domain and parsed.netloc != domain:
                continue
            if abs_url not in visited and abs_url not in queue:
                queue.append(abs_url)

        time.sleep(0.3)  # Be polite

    return hits


# ── main execute ─────────────────────────────────────────────────────────────

def execute(name: str, args: dict) -> dict:

    if name == "wiki_lookup":
        query = args["query"]
        lang = args.get("lang", "zh")
        full = bool(args.get("full", False))

        try:
            data = _wiki_summary(query, lang)
        except Exception as e:
            return {"ok": False, "result": f"Wikipedia 请求失败: {e}"}

        if not data or data.get("type") == "disambiguation":
            # Try search fallback
            try:
                results = _wiki_search(query, lang)
            except Exception:
                results = []
            if not results:
                return {"ok": True, "result": f"Wikipedia 未找到「{query}」相关词条"}
            # Try top result
            top = results[0]["title"]
            try:
                data = _wiki_summary(top, lang)
            except Exception:
                pass

        if not data:
            return {"ok": True, "result": f"未找到「{query}」的 Wikipedia 词条"}

        title = data.get("title", query)
        description = data.get("description", "")
        extract = data.get("extract", "")
        wiki_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

        if full:
            try:
                full_text = _wiki_full(title, lang)
                if full_text:
                    extract = full_text
            except Exception:
                pass

        lines = [f"📖 Wikipedia: {title}"]
        if description:
            lines.append(f"   {description}")
        lines.append("")
        lines.append(extract[:5000] if extract else "(无内容)")
        if wiki_url:
            lines.append(f"\n🔗 {wiki_url}")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "scrape_table":
        url = args["url"]
        table_index = int(args.get("table_index", 0))
        max_rows = min(int(args.get("max_rows", 30)), 100)

        try:
            html = _fetch(url)
        except Exception as e:
            return {"ok": False, "result": f"页面获取失败: {e}"}

        parser = _TableParser()
        parser.feed(html)
        tables = parser.tables

        if not tables:
            return {"ok": True, "result": f"页面 {url} 中未发现 HTML 表格"}

        if table_index == -1:
            # All tables
            lines = [f"🗃️ 共找到 {len(tables)} 张表格"]
            for i, t in enumerate(tables):
                lines += [f"\n【表格 {i}】（{len(t)} 行 × {max(len(r) for r in t)} 列）", _render_table(t, max_rows)]
            return {"ok": True, "result": "\n".join(lines)}

        if table_index >= len(tables):
            return {"ok": False, "result": f"页面只有 {len(tables)} 张表格（索引 0-{len(tables)-1}）"}

        t = tables[table_index]
        header = f"🗃️ 表格 {table_index}（{len(t)} 行 × {max(len(r) for r in t)} 列）"
        return {"ok": True, "result": f"{header}\n{_render_table(t, max_rows)}"}

    if name == "crawl_site":
        start_url = args["start_url"]
        keyword = args["keyword"]
        max_pages = min(int(args.get("max_pages", 10)), 30)
        same_domain = bool(args.get("same_domain", True))

        try:
            hits = _crawl(start_url, keyword, max_pages, same_domain)
        except Exception as e:
            return {"ok": False, "result": f"爬取失败: {e}"}

        if not hits:
            return {
                "ok": True,
                "result": f"爬取了最多 {max_pages} 个页面，未找到包含「{keyword}」的内容",
            }

        lines = [f"🕷️ 爬取结果：找到 {len(hits)} 个包含「{keyword}」的页面", ""]
        for i, h in enumerate(hits, 1):
            lines += [
                f"{i}. {h['url']}",
                f"   …{h['snippet']}…",
                "",
            ]
        return {"ok": True, "result": "\n".join(lines)}

    if name == "compare_sources":
        from concurrent.futures import ThreadPoolExecutor

        urls = args.get("urls", [])[:6]
        focus = args.get("focus", "")
        if not urls:
            return {"ok": False, "result": "请提供至少一个 URL"}

        def _fetch_one(url):
            try:
                html = _fetch(url, timeout=12)
                text = _extract_text(html, max_chars=2000)
                return {"url": url, "text": text, "ok": True}
            except Exception as e:
                return {"url": url, "text": str(e), "ok": False}

        with ThreadPoolExecutor(max_workers=min(len(urls), 4)) as ex:
            results = list(ex.map(_fetch_one, urls))

        lines = [f"🔀 多源对比（{len(urls)} 个来源）" + (f" — 关注点：{focus}" if focus else "")]
        for r in results:
            status = "✅" if r["ok"] else "❌"
            domain = urlparse(r["url"]).netloc
            lines += ["", f"{status} {domain}", f"URL: {r['url']}"]
            if r["ok"]:
                lines.append(r["text"][:1500])
            else:
                lines.append(f"获取失败: {r['text']}")

        return {"ok": True, "result": "\n".join(lines)}

    return {"ok": False, "result": f"Unknown tool: {name}"}
