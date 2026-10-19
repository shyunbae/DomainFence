import io
import json
import urllib.error
import urllib.request

import pytest

from agent.search import (
    SearchClient,
    SearchError,
    SearchResult,
    brave_provider,
    normalize_query,
)


def _results(k):
    return [SearchResult(f"t{i}", f"https://e{i}.com/", f"s{i}") for i in range(k)]


class Counting:
    def __init__(self, k=10):
        self.calls = 0
        self.k = k

    def __call__(self, q):
        self.calls += 1
        return _results(self.k)


def test_normalize_query():
    assert normalize_query("  Hello   WORLD\t") == "hello world"


def test_cache_hit_ignores_case_and_spacing(tmp_path):
    p = Counting()
    c = SearchClient(tmp_path, p)
    a = c.search("Foo  Bar")
    b = c.search(" foo bar ")
    assert p.calls == 1
    assert a == b


def test_truncates_to_n(tmp_path):
    c = SearchClient(tmp_path, Counting(10), n=3)
    assert len(c.search("q")) == 3


def test_allow_filters_before_truncation(tmp_path):
    c = SearchClient(tmp_path, Counting(10), n=3)
    keep = {"e5.com", "e7.com", "e9.com", "e8.com"}
    out = c.search("q", allow=lambda host: host in keep)
    assert [r.url for r in out] == ["https://e5.com/", "https://e7.com/", "https://e8.com/"]
    # cache still holds the full unfiltered list for other arms
    assert len(SearchClient(tmp_path, Counting(10), n=10).search("q")) == 10


def test_allow_filters_cached_results_too(tmp_path):
    p = Counting(10)
    c = SearchClient(tmp_path, p, n=8)
    c.search("q")
    out = c.search("q", allow=lambda host: host == "e2.com")
    assert p.calls == 1 and [r.url for r in out] == ["https://e2.com/"]


def test_cache_persists_across_clients(tmp_path):
    p1 = Counting(4)
    SearchClient(tmp_path, p1).search("q")
    p2 = Counting(4)
    out = SearchClient(tmp_path, p2).search("Q")
    assert p2.calls == 0
    assert out == _results(4)[:8]
    data = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert data["query"] == "q" and data["results"][0]["url"] == "https://e0.com/"


def test_provider_error_not_cached(tmp_path):
    def bad(q):
        raise RuntimeError("boom")

    with pytest.raises(SearchError):
        SearchClient(tmp_path, bad).search("q")
    assert list(tmp_path.glob("*")) == []


def test_brave_requires_key(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    with pytest.raises(SearchError):
        brave_provider("q")


def test_brave_maps_results(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "k")
    seen = {}
    body = json.dumps(
        {"web": {"results": [{"title": "T", "url": "https://a.com/", "description": "D"}]}}
    ).encode()

    def fake(req, timeout=None):
        seen["url"] = req.full_url
        seen["tok"] = req.get_header("X-subscription-token")
        return io.BytesIO(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = brave_provider("a b")
    assert out == [SearchResult("T", "https://a.com/", "D")]
    assert seen["tok"] == "k" and "q=a+b" in seen["url"] and "count=10" in seen["url"]


def _http429():
    return urllib.error.HTTPError("https://x", 429, "Too Many Requests", {}, None)


def test_brave_retries_once_on_429(monkeypatch):
    import agent.search as S
    monkeypatch.setenv("BRAVE_API_KEY", "k")
    sleeps, calls = [], []
    body = json.dumps({"web": {"results": [{"title": "T", "url": "u", "description": "D"}]}}).encode()

    def fake(req, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            raise _http429()
        return io.BytesIO(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(S.time, "sleep", sleeps.append)
    assert brave_provider("q") == [SearchResult("T", "u", "D")]
    assert sleeps == [2] and len(calls) == 2


def test_brave_429_twice_raises(monkeypatch):
    import agent.search as S
    monkeypatch.setenv("BRAVE_API_KEY", "k")
    calls = []

    def fake(req, timeout=None):
        calls.append(1)
        raise _http429()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)
    with pytest.raises(SearchError):
        brave_provider("q")
    assert len(calls) == 2


def test_extra_results_prepended_before_filter_and_truncation(tmp_path):
    c = SearchClient(tmp_path, Counting(2), n=2)
    extra = [SearchResult("poison", "https://evil.test/x", "s")]
    out = c.search("q", extra=extra)
    assert [r.url for r in out] == ["https://evil.test/x", "https://e0.com/"]  # prepended, truncated to n
    # a fence that blocks the attacker host drops the extra result
    kept = c.search("q", allow=lambda h: h != "evil.test", extra=extra)
    assert all("evil.test" not in r.url for r in kept)
