"""Pure route decision for the Playwright fence."""
from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from agent.fence import Fence, canonical_host

Decision = Literal["block", "sink", "inject", "pass"]


def decide(url: str, is_document: bool, fence: Fence, attacker_hosts: set[str],
           inject_fence: Fence, attack: str) -> Decision:
    """Fence first, then attacker sink, then injection, else pass through."""
    host = urlsplit(url).hostname
    if not host:
        return "block" if is_document else "pass"
    if is_document and not fence.allows(host):
        return "block"
    if canonical_host(host) in {canonical_host(a) for a in attacker_hosts}:
        return "sink"
    if is_document and attack != "none" and inject_fence.allows(host):
        return "inject"
    return "pass"
