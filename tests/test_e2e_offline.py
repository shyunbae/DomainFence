"""Offline end-to-end tests for FencedBrowser against a local fixture server."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.async_api import Error as PlaywrightError

from agent.browser import FencedBrowser
from agent.fence import Fence
from tests.fixtures.sites import ATTACKER, PDF_BYTES, start_server

pytestmark = pytest.mark.e2e

EXTRA_RULES = "MAP seed.test 127.0.0.1, MAP partner.test 127.0.0.1"
ALLOWED_HOSTS = {"seed.test", "partner.test", ATTACKER}
SEEN_HOSTS: set[str] = set()


@pytest.fixture
async def port():
    runner, p = await start_server()
    yield p
    await runner.cleanup()


def make_browser(fence: Fence, attack: str = "none") -> FencedBrowser:
    return FencedBrowser(
        fence, "seed.test", [], attack, None, [ATTACKER],
        extra_resolver_rules=EXTRA_RULES, min_interval_s=0,
    )


def record_hosts(b: FencedBrowser) -> None:
    b.context.on("request", lambda req: SEEN_HOSTS.add(urlsplit(req.url).hostname))


def element_id(text: str, needle: str) -> int:
    for line in text.splitlines():
        m = re.match(r"\[(\d+)\] ", line)
        if m and needle in line:
            return int(m.group(1))
    raise AssertionError(f"no element matching {needle!r} in:\n{text}")


def host(url: str) -> str | None:
    return urlsplit(url).hostname


async def test_apex_blocks_injected_link(port):
    async with make_browser(Fence.apex("seed.test", []), "visible_link") as b:
        record_hosts(b)
        assert await b.start(f"http://seed.test:{port}/") == "ok"
        obs = await b.observe()
        res = await b.act({"action": "click", "id": element_id(obs.text, ATTACKER)})
        assert res.startswith("blocked:")
        blocks = [e for e in b.events if e["type"] == "block"]
        assert len(blocks) == 1 and blocks[0]["host"] == ATTACKER and blocks[0]["attacker"] is True
        assert not any(e["type"] == "sink_hit" for e in b.events)
        assert host((await b.observe()).url) == "seed.test"


async def test_none_reaches_sink(port):
    async with make_browser(Fence.none(), "visible_link") as b:
        record_hosts(b)
        await b.start(f"http://seed.test:{port}/")
        obs = await b.observe()
        assert await b.act({"action": "click", "id": element_id(obs.text, ATTACKER)}) == "ok"
        assert any(e["type"] == "sink_hit" and e["attacker"] is True for e in b.events)
        assert "Verification required" in (await b.observe()).text


@pytest.mark.parametrize("attack", ["none", "visible_link"])
async def test_server_redirect_caught(port, attack):
    async with make_browser(Fence.apex("seed.test", []), attack) as b:
        record_hosts(b)
        await b.start(f"http://seed.test:{port}/")
        res = await b.act({"action": "goto", "url": f"http://seed.test:{port}/redirect"})
        assert res.startswith("blocked:")
        blocks = [e for e in b.events if e["type"] == "block"]
        assert len(blocks) == 1 and blocks[0]["host"] == ATTACKER and blocks[0]["attacker"]
        assert host((await b.observe()).url) == "seed.test"


async def test_offfence_start_ends_blank(port):
    # Redirected first navigation: going back lands on the initial about:blank entry.
    async with make_browser(Fence.apex("seed.test", [])) as b:
        record_hosts(b)
        res = await b.start(f"http://seed.test:{port}/redirect")
        assert res == f"blocked: {ATTACKER} not in allow-list"
        assert [e["host"] for e in b.events if e["type"] == "block"] == [ATTACKER]
        obs = await b.observe()
        assert obs.url == "about:blank" and "attacker portal" not in obs.text


async def test_failed_go_back_falls_back_to_blank(port):
    async with make_browser(Fence.apex("seed.test", [])) as b:
        record_hosts(b)
        await b.start(f"http://seed.test:{port}/")

        async def broken_go_back(*a, **k):
            raise PlaywrightError("forced go_back failure")

        b.page.go_back = broken_go_back
        res = await b.act({"action": "goto", "url": f"http://seed.test:{port}/redirect"})
        assert res.startswith("blocked:")
        obs = await b.observe()
        assert obs.url == "about:blank" and "attacker portal" not in obs.text


async def test_popup_followed_only_if_allowed(port):
    async with make_browser(Fence.apex("seed.test", [])) as b:
        record_hosts(b)
        await b.start(f"http://seed.test:{port}/")
        obs = await b.observe()
        res = await b.act({"action": "click", "id": element_id(obs.text, "'Partner'")})
        assert res.startswith("blocked:")
        assert [e["host"] for e in b.events if e["type"] == "block"] == ["partner.test"]
        assert b.context.pages == [b.page]
        assert host((await b.observe()).url) == "seed.test"
    async with make_browser(Fence.none()) as b:
        record_hosts(b)
        await b.start(f"http://seed.test:{port}/")
        obs = await b.observe()
        assert await b.act({"action": "click", "id": element_id(obs.text, "'Partner'")}) == "ok"
        assert b.context.pages == [b.page]
        obs = await b.observe()
        assert host(obs.url) == "partner.test" and "partner page" in obs.text


async def test_pdf_observation(port):
    async with make_browser(Fence.apex("seed.test", [])) as b:
        record_hosts(b)
        await b.start(f"http://seed.test:{port}/")
        assert await b.act({"action": "goto", "url": f"http://seed.test:{port}/doc.pdf"}) == "ok"
        obs = await b.observe()
        assert obs.text.startswith("non-HTML document (application/pdf)")
        assert obs.url == f"http://seed.test:{port}/doc.pdf"
        assert await b.act({"action": "back"}) == "ok"
        assert "Seed University" in (await b.observe()).text


async def test_pdf_bytes_unchanged_under_attack(port):
    async with make_browser(Fence.apex("seed.test", []), "visible_link") as b:
        record_hosts(b)
        await b.start(f"http://seed.test:{port}/")
        async with b.page.expect_download() as info:
            await b.act({"action": "goto", "url": f"http://seed.test:{port}/doc.pdf"})
        download = await info.value
        assert Path(await download.path()).read_bytes() == PDF_BYTES


async def test_unknown_element_id(port):
    async with make_browser(Fence.apex("seed.test", [])) as b:
        await b.start(f"http://seed.test:{port}/")
        await b.observe()
        assert await b.act({"action": "click", "id": 9999}) == "error: unknown element id 9999"


async def test_no_request_leaves_localhost(port):
    # Runs after the tests above (file order) and also exercises the fence itself.
    for fence in (Fence.none(), Fence.apex("seed.test", [])):
        async with make_browser(fence, "visible_link") as b:
            record_hosts(b)
            await b.start(f"http://seed.test:{port}/")
            obs = await b.observe()
            await b.act({"action": "click", "id": element_id(obs.text, ATTACKER)})
            await b.act({"action": "goto", "url": f"http://seed.test:{port}/redirect"})
    assert SEEN_HOSTS and SEEN_HOSTS <= ALLOWED_HOSTS


async def test_blank_start_then_goto(port):
    async with make_browser(Fence.apex("seed.test", [])) as b:
        record_hosts(b)
        assert await b.start("about:blank") == "ok"
        obs = await b.observe()
        assert obs.url == "about:blank" and not obs.challenge
        assert await b.act({"action": "goto", "url": f"http://seed.test:{port}/"}) == "ok"
        assert (await b.observe()).url.startswith(f"http://seed.test:{port}/")
        assert b.events == []
