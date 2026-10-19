from __future__ import annotations

import asyncio
import time

import pytest

from agent import browser as B
from agent.browser import FencedBrowser
from agent.fence import Fence


@pytest.fixture(autouse=True)
def _reset_throttle():
    B._LAST_DOC.clear()
    yield
    B._LAST_DOC.clear()


async def test_throttle_spaces_concurrent_requests_to_same_host():
    b = FencedBrowser(Fence.none(), "seed.test", [], "none", None, [], min_interval_s=0.2)
    ends: list[float] = []

    async def one(host):
        await b._throttle(host)
        ends.append(time.monotonic())

    await asyncio.gather(one("seed.test"), one("www.Seed.test"), one("seed.test"))
    ends.sort()
    assert ends[1] - ends[0] >= 0.19 and ends[2] - ends[1] >= 0.19


async def test_throttle_does_not_delay_other_hosts():
    b = FencedBrowser(Fence.none(), "seed.test", [], "none", None, [], min_interval_s=5)
    t0 = time.monotonic()
    await asyncio.gather(b._throttle("seed.test"), b._throttle("partner.test"))
    assert time.monotonic() - t0 < 1


async def test_throttle_state_persists_across_browser_instances():
    a = FencedBrowser(Fence.none(), "seed.test", [], "none", None, [], min_interval_s=0.2)
    b = FencedBrowser(Fence.none(), "seed.test", [], "none", None, [], min_interval_s=0.2)
    await a._throttle("seed.test")
    t0 = time.monotonic()
    await b._throttle("seed.test")
    assert time.monotonic() - t0 >= 0.19
