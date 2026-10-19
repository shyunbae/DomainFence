"""Disk-cached web search client."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchError(Exception):
    """Raised when the search provider fails."""


def normalize_query(q: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    return " ".join(q.lower().split())


class SearchClient:
    """Caches provider results on disk, keyed by the normalized query."""

    def __init__(
        self,
        cache_dir: Path,
        provider: Callable[[str], list[SearchResult]],
        n: int = 8,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.provider = provider
        self.n = n

    def _path(self, norm: str) -> Path:
        return self.cache_dir / f"{hashlib.sha1(norm.encode('utf-8')).hexdigest()}.json"

    def search(self, query: str, allow: Callable[[str], bool] | None = None,
               extra: list[SearchResult] = ()) -> list[SearchResult]:
        """Return up to n results. `extra` is prepended to the fetched list (e.g. an injected
        result); `allow(host)` then filters the whole list; finally it is truncated to n."""
        results = [*extra, *self._fetch(query)]
        if allow is not None:
            results = [r for r in results if allow(urlsplit(r.url).hostname or "")]
        return results[: self.n]

    def _fetch(self, query: str) -> list[SearchResult]:
        norm = normalize_query(query)
        path = self._path(norm)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return [SearchResult(**r) for r in data["results"]]
        try:
            results = list(self.provider(norm))
        except SearchError:
            raise
        except Exception as e:
            raise SearchError(f"search failed for {norm!r}: {e}") from e
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "query": norm,
            "results": [
                {"title": r.title, "url": r.url, "snippet": r.snippet} for r in results
            ],
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return results


def brave_provider(query: str) -> list[SearchResult]:
    """Query the Brave Search API (needs BRAVE_API_KEY)."""
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        raise SearchError("BRAVE_API_KEY is not set")
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {"q": query, "count": 10}
    )
    req = urllib.request.Request(
        url, headers={"X-Subscription-Token": key, "Accept": "application/json"}
    )
    data = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                time.sleep(2)
                continue
            raise SearchError(f"brave request failed: {e}") from e
        except Exception as e:
            raise SearchError(f"brave request failed: {e}") from e
    return [
        SearchResult(
            title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("description", "")
        )
        for r in data.get("web", {}).get("results", [])
    ]
