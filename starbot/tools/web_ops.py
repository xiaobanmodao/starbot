import httpx
from bs4 import BeautifulSoup
from . import tool


@tool(
    name="web_search",
    description="Search the web using DuckDuckGo and return results.",
    params={
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"],
    },
)
async def web_search(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
            )
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for item in soup.select(".result")[:5]:
            title_el = item.select_one(".result__title")
            snippet_el = item.select_one(".result__snippet")
            link_el = item.select_one(".result__url")
            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            if title:
                results.append(f"{title}\n  {link}\n  {snippet}")
        return "\n\n".join(results) if results else "No results found"
    except Exception as e:
        return f"[error] {e}"
