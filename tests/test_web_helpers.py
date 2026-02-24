from types import SimpleNamespace

from actions import web_helpers


def setup_function():
    # Isolate in-memory cache across tests.
    web_helpers._page_cache.clear()


def test_do_web_search_uses_ddg_results(monkeypatch):
    ddg_results = [{"title": "A", "url": "https://a.test", "snippet": "x"}]

    monkeypatch.setattr(web_helpers, "search_ddg", lambda q: ddg_results)
    monkeypatch.setattr(web_helpers, "search_bing", lambda q: [{"title": "B"}])

    got = web_helpers.do_web_search("query")
    assert got == ddg_results


def test_do_web_search_falls_back_to_bing(monkeypatch):
    bing_results = [{"title": "B", "url": "https://b.test", "snippet": ""}]

    monkeypatch.setattr(web_helpers, "search_ddg", lambda q: [])
    monkeypatch.setattr(web_helpers, "search_bing", lambda q: bing_results)

    got = web_helpers.do_web_search("query")
    assert got == bing_results


def test_fetch_url_text_caches_success(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, headers=None, timeout=None):
        calls["n"] += 1
        return SimpleNamespace(text="<html><body>hello</body></html>", apparent_encoding="utf-8", encoding=None)

    monkeypatch.setattr(web_helpers.requests, "get", fake_get)
    monkeypatch.setattr(web_helpers, "extract_html_text", lambda html: "hello")

    first = web_helpers.fetch_url_text("https://example.com")
    second = web_helpers.fetch_url_text("https://example.com")

    assert first == "hello"
    assert second == "hello"
    assert calls["n"] == 1


def test_fetch_url_text_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("temporary")
        return SimpleNamespace(text="<html>ok</html>", apparent_encoding="utf-8", encoding=None)

    monkeypatch.setattr(web_helpers.requests, "get", fake_get)
    monkeypatch.setattr(web_helpers, "extract_html_text", lambda html: "ok")
    monkeypatch.setattr(web_helpers.time, "sleep", lambda s: None)

    got = web_helpers.fetch_url_text("https://retry.test")
    assert got == "ok"
    assert calls["n"] == 3


def test_fetch_url_text_returns_empty_after_retries(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, headers=None, timeout=None):
        calls["n"] += 1
        raise RuntimeError("down")

    monkeypatch.setattr(web_helpers.requests, "get", fake_get)
    monkeypatch.setattr(web_helpers.time, "sleep", lambda s: None)

    got = web_helpers.fetch_url_text("https://down.test")
    assert got == ""
    assert calls["n"] == 3


def test_extract_html_text_fallback_when_trafilatura_returns_none(monkeypatch):
    fake_trafilatura = SimpleNamespace(extract=lambda *a, **k: None)
    monkeypatch.setitem(__import__("sys").modules, "trafilatura", fake_trafilatura)

    html = """
    <html><head><script>bad()</script></head>
    <body><h1>Title</h1><p>Alpha</p><div>Beta</div></body></html>
    """

    got = web_helpers.extract_html_text(html)
    assert "Title" in got
    assert "Alpha" in got
    assert "Beta" in got
    assert "bad()" not in got


def test_extract_html_text_prefers_trafilatura_when_long_text(monkeypatch):
    long_text = ("Line\n" * 60).strip()
    fake_trafilatura = SimpleNamespace(extract=lambda *a, **k: long_text)
    monkeypatch.setitem(__import__("sys").modules, "trafilatura", fake_trafilatura)

    got = web_helpers.extract_html_text("<html><body>ignored</body></html>")
    assert got == long_text

