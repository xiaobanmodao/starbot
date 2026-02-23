"""News aggregation skill — RSS feeds + HackerNews API, no API key needed."""

META = {
    "name": "news",
    "version": "1.0.0",
    "description": "新闻聚合：按分类获取最新头条、解析任意 RSS 源、HackerNews 热帖",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_headlines",
            "description": (
                "获取指定分类的最新新闻头条。"
                "分类：tech（科技）/ world（国际）/ china（国内）/ "
                "finance（财经）/ science（科学）/ sports（体育）/ ai（AI资讯）"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "新闻分类：tech / world / china / finance / science / sports / ai",
                        "default": "tech",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "返回条数，默认 10，最多 30",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_rss",
            "description": "解析指定的 RSS / Atom 订阅源，返回最新文章列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "feed_url": {"type": "string", "description": "RSS/Atom 订阅源的 URL"},
                    "max_items": {
                        "type": "integer",
                        "description": "返回条数，默认 10",
                        "default": 10,
                    },
                },
                "required": ["feed_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hacker_news",
            "description": "获取 HackerNews 热门故事，包含标题、评分、评论数、链接",
            "parameters": {
                "type": "object",
                "properties": {
                    "feed_type": {
                        "type": "string",
                        "description": "类型：top（最热）/ new（最新）/ best（最佳），默认 top",
                        "default": "top",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "返回条数，默认 10，最多 30",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "在多个新闻源中搜索包含特定关键词的最新报道",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "lang": {
                        "type": "string",
                        "description": "语言：zh（中文源）/ en（英文源）/ all（全部），默认 all",
                        "default": "all",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "返回条数，默认 10",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
]

_FEEDS = {
    "tech": [
        ("TechCrunch",     "https://techcrunch.com/feed/"),
        ("The Verge",      "https://www.theverge.com/rss/index.xml"),
        ("Wired",          "https://www.wired.com/feed/rss"),
    ],
    "ai": [
        ("MIT Tech Review","https://www.technologyreview.com/feed/"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
        ("Google AI Blog", "https://blog.google/technology/ai/rss/"),
    ],
    "world": [
        ("BBC World",      "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters",        "https://feeds.reuters.com/reuters/worldNews"),
        ("AP News",        "https://rsshub.app/apnews/topics/ap-top-news"),
    ],
    "china": [
        ("新华社",          "https://www.xinhuanet.com/rss/news.xml"),
        ("36Kr",           "https://36kr.com/feed"),
        ("虎嗅",           "https://www.huxiu.com/rss/0.xml"),
    ],
    "finance": [
        ("Financial Times", "https://www.ft.com/rss/home/cn"),
        ("彭博社",          "https://feeds.bloomberg.com/markets/news.rss"),
        ("华尔街见闻",      "https://rsshub.app/wallstreetcn/news/global"),
    ],
    "science": [
        ("Nature",         "https://www.nature.com/nature.rss"),
        ("Science Daily",  "https://www.sciencedaily.com/rss/top/science.xml"),
        ("NASA",           "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    ],
    "sports": [
        ("ESPN",           "https://www.espn.com/espn/rss/news"),
        ("BBC Sport",      "https://feeds.bbci.co.uk/sport/rss.xml"),
    ],
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Starbot/1.0; +https://github.com/starbot)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
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


def _parse_rss(url: str, max_items: int = 10) -> list[dict]:
    import requests
    import xml.etree.ElementTree as ET
    from html import unescape
    import re

    r = requests.get(url, headers=_HEADERS, proxies=_get_proxies(), timeout=10)
    r.raise_for_status()
    r.encoding = "utf-8"

    # Strip namespaces for simpler parsing
    content = re.sub(r' xmlns[^"]*"[^"]*"', "", r.text)
    content = re.sub(r"<[a-zA-Z]+:[a-zA-Z]+", lambda m: "<" + m.group().split(":")[-1], content)
    content = re.sub(r"</[a-zA-Z]+:[a-zA-Z]+>", lambda m: "</" + m.group().split(":")[-1] + ">", content)

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    items = []
    # Try RSS
    for item in root.iter("item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        pub = item.findtext("pubDate") or item.findtext("date") or ""
        desc = item.findtext("description") or item.findtext("summary") or ""
        # Clean HTML from description
        desc = re.sub(r"<[^>]+>", "", unescape(desc)).strip()[:200]
        items.append({
            "title": unescape(title).strip(),
            "link": link.strip(),
            "published": pub[:25],
            "summary": desc,
        })
        if len(items) >= max_items:
            break

    # Try Atom if no items
    if not items:
        for entry in root.iter("entry"):
            title = entry.findtext("title") or ""
            link_el = entry.find("link")
            link = link_el.get("href", "") if link_el is not None else ""
            pub = entry.findtext("published") or entry.findtext("updated") or ""
            summary = entry.findtext("summary") or entry.findtext("content") or ""
            summary = re.sub(r"<[^>]+>", "", unescape(summary)).strip()[:200]
            items.append({
                "title": unescape(title).strip(),
                "link": link.strip(),
                "published": pub[:25],
                "summary": summary,
            })
            if len(items) >= max_items:
                break

    return items


def _fmt_items(source: str, items: list[dict]) -> str:
    if not items:
        return f"  ({source}: 无内容)"
    lines = []
    for i, item in enumerate(items, 1):
        title = item["title"][:80]
        pub = item["published"][:16] if item["published"] else ""
        summary = item["summary"][:120] if item["summary"] else ""
        lines.append(f"  {i:2}. {title}")
        if pub:
            lines.append(f"      📅 {pub}")
        if summary:
            lines.append(f"      {summary}…")
        lines.append(f"      🔗 {item['link'][:80]}")
    return "\n".join(lines)


def execute(name: str, args: dict) -> dict:

    if name == "get_headlines":
        category = args.get("category", "tech").lower()
        max_items = min(int(args.get("max_items", 10)), 30)

        feeds = _FEEDS.get(category, _FEEDS["tech"])
        if not feeds:
            return {"ok": False, "result": f"不支持的分类: {category}，可选: {', '.join(_FEEDS.keys())}"}

        from concurrent.futures import ThreadPoolExecutor

        def _try_feed(src_url):
            src, url = src_url
            try:
                items = _parse_rss(url, max_items // len(feeds) + 2)
                return src, items
            except Exception as e:
                return src, []

        with ThreadPoolExecutor(max_workers=len(feeds)) as ex:
            results = list(ex.map(_try_feed, feeds))

        cat_labels = {
            "tech": "科技", "world": "国际", "china": "国内",
            "finance": "财经", "science": "科学", "sports": "体育", "ai": "AI 资讯",
        }
        label = cat_labels.get(category, category)
        all_items = []
        for _, items in results:
            all_items.extend(items)

        # Sort by recency (best-effort) and deduplicate by title
        seen = set()
        deduped = []
        for item in all_items:
            key = item["title"][:40]
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        deduped = deduped[:max_items]
        lines = [f"📰 {label}新闻 Top {len(deduped)}:", ""]
        for i, item in enumerate(deduped, 1):
            lines.append(f"{i:2}. {item['title'][:90]}")
            if item["published"]:
                lines.append(f"    📅 {item['published'][:16]}")
            if item["summary"]:
                lines.append(f"    {item['summary'][:100]}…")
            lines.append(f"    🔗 {item['link'][:80]}")
            lines.append("")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "fetch_rss":
        feed_url = args["feed_url"]
        max_items = min(int(args.get("max_items", 10)), 50)
        try:
            items = _parse_rss(feed_url, max_items)
        except Exception as e:
            return {"ok": False, "result": f"RSS 解析失败: {e}"}

        if not items:
            return {"ok": True, "result": f"RSS 源 {feed_url} 无法解析或没有内容"}

        lines = [f"📡 RSS 源：{feed_url}", f"共 {len(items)} 条，", ""]
        lines.append(_fmt_items("", items))
        return {"ok": True, "result": "\n".join(lines)}

    if name == "hacker_news":
        import requests

        feed_type = args.get("feed_type", "top")
        max_items = min(int(args.get("max_items", 10)), 30)
        endpoint_map = {"top": "topstories", "new": "newstories", "best": "beststories"}
        endpoint = endpoint_map.get(feed_type, "topstories")

        try:
            r = requests.get(
                f"https://hacker-news.firebaseio.com/v0/{endpoint}.json",
                proxies=_get_proxies(),
                timeout=10,
            )
            ids = r.json()[:max_items]
        except Exception as e:
            return {"ok": False, "result": f"HackerNews 请求失败: {e}"}

        from concurrent.futures import ThreadPoolExecutor

        def _fetch_story(story_id):
            try:
                r = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    proxies=_get_proxies(),
                    timeout=8,
                )
                return r.json()
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=10) as ex:
            stories = list(ex.map(_fetch_story, ids))

        label = {"top": "热门", "new": "最新", "best": "最佳"}.get(feed_type, "热门")
        lines = [f"🧡 Hacker News {label}（{len(stories)} 条）", ""]
        for i, s in enumerate(stories, 1):
            if not s:
                continue
            title = s.get("title", "(无标题)")[:90]
            score = s.get("score", 0)
            comments = s.get("descendants", 0)
            url = s.get("url", f"https://news.ycombinator.com/item?id={s.get('id')}")
            lines.append(f"{i:2}. {title}")
            lines.append(f"    ⬆ {score} 分  💬 {comments} 评论")
            lines.append(f"    🔗 {url[:80]}")
            lines.append("")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "search_news":
        query = args["query"].lower()
        lang = args.get("lang", "all").lower()
        max_items = min(int(args.get("max_items", 10)), 30)

        # Select feeds based on lang preference
        if lang == "zh":
            feed_pool = _FEEDS["china"] + _FEEDS["finance"][:1]
        elif lang == "en":
            feed_pool = _FEEDS["tech"] + _FEEDS["world"] + _FEEDS["ai"]
        else:
            feed_pool = [f for cat in _FEEDS.values() for f in cat]

        from concurrent.futures import ThreadPoolExecutor

        def _search_feed(src_url):
            src, url = src_url
            try:
                items = _parse_rss(url, 50)
                return [
                    {**item, "source": src}
                    for item in items
                    if query in item["title"].lower() or query in item["summary"].lower()
                ]
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=6) as ex:
            all_results = []
            for hits in ex.map(_search_feed, feed_pool):
                all_results.extend(hits)

        # Deduplicate
        seen, deduped = set(), []
        for item in all_results:
            key = item["title"][:40]
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        deduped = deduped[:max_items]
        if not deduped:
            return {"ok": True, "result": f"在已订阅的新闻源中未找到包含「{query}」的报道"}

        lines = [f"🔍 新闻搜索「{query}」，共 {len(deduped)} 条结果:", ""]
        for i, item in enumerate(deduped, 1):
            src = item.get("source", "")
            lines.append(f"{i:2}. [{src}] {item['title'][:80]}")
            if item["published"]:
                lines.append(f"    📅 {item['published'][:16]}")
            if item["summary"]:
                lines.append(f"    {item['summary'][:100]}…")
            lines.append(f"    🔗 {item['link'][:80]}")
            lines.append("")

        return {"ok": True, "result": "\n".join(lines)}

    return {"ok": False, "result": f"Unknown tool: {name}"}
