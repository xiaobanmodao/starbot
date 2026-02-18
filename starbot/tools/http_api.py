import httpx
import json
from . import tool


@tool(
    name="http_request",
    description="Make an HTTP request (GET/POST/PUT/DELETE) and return the response.",
    params={
        "properties": {
            "method": {"type": "string", "description": "HTTP method (GET/POST/PUT/DELETE)"},
            "url": {"type": "string", "description": "Request URL"},
            "headers": {"type": "object", "description": "Optional headers"},
            "body": {"type": "string", "description": "Optional request body (JSON string)"},
        },
        "required": ["method", "url"],
    },
)
async def http_request(method: str, url: str, headers: dict = None, body: str = None) -> str:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            kwargs = {}
            if headers:
                kwargs["headers"] = headers
            if body:
                kwargs["content"] = body
                kwargs.setdefault("headers", {})["Content-Type"] = "application/json"
            r = await getattr(c, method.lower())(url, **kwargs)
        text = r.text[:5000]
        return f"[{r.status_code}]\n{text}"
    except Exception as e:
        return f"[error] {e}"
