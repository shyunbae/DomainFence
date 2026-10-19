"""Host allow-list fences for the agent experiment."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Literal

from related_domains import RankedHost


def canonical_host(host: str) -> str:
    """Lowercase, strip port, trailing dot and one leading www., IDNA-encode."""
    h = host.strip().lower()
    if h.count(":") == 1:
        h = h.split(":", 1)[0]
    h = h.rstrip(".")
    if h.startswith("www."):
        h = h[4:]
    try:
        h.encode("ascii")
    except UnicodeEncodeError:
        try:
            h = h.encode("idna").decode("ascii")
        except UnicodeError:
            pass
    return h


def _is_ip(h: str) -> bool:
    try:
        ipaddress.ip_address(h.strip("[]"))
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class Fence:
    name: str
    mode: Literal["none", "apex", "hosts", "hybrid"]
    domains: frozenset[str]
    hosts: frozenset[str] = frozenset()  # hybrid only: exact external hosts

    def allows(self, host: str) -> bool:
        if self.mode == "none":
            return True
        h = canonical_host(host)
        if not h or _is_ip(h):
            return False
        if self.mode in ("apex", "hybrid"):
            if any(h == d or h.endswith("." + d) for d in self.domains):
                return True
            return self.mode == "hybrid" and h in self.hosts
        return h in self.domains

    @classmethod
    def none(cls) -> Fence:
        return cls("none", "none", frozenset())

    @classmethod
    def apex(cls, seed: str, aliases: list[str]) -> Fence:
        return cls("apex", "apex", frozenset(canonical_host(d) for d in [seed, *aliases]))

    @classmethod
    def ppr(cls, ranking: list[RankedHost], k: int) -> Fence:
        if k < 1:
            raise ValueError("k must be >= 1")
        return cls(f"ppr{k}", "hosts", frozenset(canonical_host(r.host) for r in ranking[:k]))

    @classmethod
    def hybrid(cls, seed: str, aliases: list[str], ranking: list[RankedHost], k: int) -> Fence:
        """Apex rule for the seed and aliases, plus the top-k external hosts by PPR score."""
        if k < 1:
            raise ValueError("k must be >= 1")
        external = [r for r in ranking if not r.is_first_party][:k]
        return cls(f"hyb{k}", "hybrid", frozenset(canonical_host(d) for d in [seed, *aliases]),
                   frozenset(canonical_host(r.host) for r in external))
