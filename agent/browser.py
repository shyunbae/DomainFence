"""Playwright browser that enforces a host fence, plants test injections and serves a local sink.

Playwright behaviors this relies on (verified against Playwright 1.64 / Chromium):
- Route handlers are NOT invoked for the hops of an HTTP redirect, so server redirects
  bypass the fence; the post-action check is the backstop.
- `route.fetch()` runs in Playwright's Node process and ignores Chromium's
  `--host-resolver-rules`. It is therefore called with `max_redirects=0` (it must never
  follow a redirect to an unfenced host over real DNS) and with MAP rules applied by hand.
- Popup navigation requests have no frame yet, so `request.frame` is never touched for them.
"""
from __future__ import annotations

import asyncio
import re
import time
from urllib.parse import urlsplit, urlunsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from agent.fence import Fence, canonical_host
from agent.injection import SINK_HTML, inject, resolver_rules
from agent.loop import Observation
from agent.routing import decide

USER_AGENT = "DomainFenceAgentResearch/0.1 (+https://github.com/shyunbae/DomainFence)"
TIMEOUT_MS = 15_000
POPUP_SETTLE_S = 0.3
CHALLENGE_RE = re.compile(r"Just a moment|Attention Required|Access denied", re.IGNORECASE)
_DROP_HEADERS = {"content-length", "content-encoding", "transfer-encoding"}

_OBSERVE_JS = r"""
() => {
  document.querySelectorAll('[data-agent-id]').forEach(e => e.removeAttribute('data-agent-id'));
  const sel = 'a, button, input, select, textarea, [role=button], [role=link]';
  const lines = [];
  let n = 0;
  for (const el of document.querySelectorAll(sel)) {
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || el.getClientRects().length === 0) continue;
    if (el.type === 'hidden') continue;
    n += 1;
    el.setAttribute('data-agent-id', String(n));
    const tag = el.tagName.toLowerCase();
    let role = el.getAttribute('role');
    if (!role) {
      if (tag === 'a') role = 'link';
      else if (tag === 'select') role = 'combobox';
      else if (tag === 'textarea') role = 'textbox';
      else if (tag === 'input') role = ['button', 'submit', 'reset', 'checkbox', 'radio'].includes(el.type) ? el.type : 'textbox';
      else role = tag;
    }
    const name = (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder
                  || el.title || el.name || '').replace(/\s+/g, ' ').trim().slice(0, 80);
    const href = tag === 'a' && el.href ? ' -> ' + el.href : '';
    lines.push(`[${n}] ${role} '${name.replace(/'/g, "\\'")}'${href}`);
  }
  const root = document.querySelector('main') || document.body;
  return {lines: lines.join('\n'), text: root ? root.innerText : '', ctype: document.contentType};
}
"""


# Per-host time of the last reserved document slot; module-level so the politeness
# interval holds across episodes (each episode builds a fresh FencedBrowser).
_LAST_DOC: dict[str, float] = {}


def _parse_map_rules(rules: str) -> dict[str, str]:
    """Exact-host `MAP host ip` entries from a Chromium host-resolver-rules string."""
    out: dict[str, str] = {}
    for part in rules.split(","):
        bits = part.split()
        if len(bits) == 3 and bits[0].upper() == "MAP" and "*" not in bits[1]:
            out[canonical_host(bits[1])] = bits[2]
    return out


def _first_line(e: BaseException) -> str:
    return (str(e).strip().splitlines() or [type(e).__name__])[0]


class FencedBrowser:
    """BrowserLike implementation over Playwright Chromium (async context manager)."""

    def __init__(self, fence: Fence, seed: str, aliases: list[str], attack: str,
                 misinfo_answer: str | None, attacker_hosts: list[str],
                 extra_resolver_rules: str = "", headless: bool = True,
                 min_interval_s: float = 1.0):
        self.fence = fence
        self.seed = seed
        self.attack = attack
        self.misinfo_answer = misinfo_answer
        self.attacker_hosts = list(attacker_hosts)
        self._attacker_set = {canonical_host(h) for h in attacker_hosts}
        self.inject_fence = Fence.apex(seed, aliases)
        self.rules = ", ".join(r for r in (resolver_rules(attacker_hosts), extra_resolver_rules) if r)
        self._map = _parse_map_rules(self.rules)
        self.headless = headless
        self.min_interval_s = min_interval_s
        self.events: list[dict] = []
        self._nav_blocks: list[str] = []  # hosts of blocked top-level navigations (main page/popups)
        self._ctypes: dict[str, str] = {}
        self._non_html: tuple[str, str] | None = None  # (content-type, url) of a downloaded main doc
        self._pw = self._browser = self.context = self.page = None

    async def __aenter__(self) -> FencedBrowser:
        self._pw = await async_playwright().start()
        args = [f"--host-resolver-rules={self.rules}"] if self.rules else []
        self._browser = await self._pw.chromium.launch(headless=self.headless, args=args)
        self.context = await self._browser.new_context(service_workers="block", user_agent=USER_AGENT)
        self.context.set_default_timeout(TIMEOUT_MS)
        self.context.set_default_navigation_timeout(TIMEOUT_MS)
        await self.context.route("**/*", self._handle)
        self.context.on("response", self._on_response)
        self.page = await self.context.new_page()
        self.page.on("download", self._on_download)
        self.page.on("framenavigated", self._on_framenavigated)
        return self

    async def __aexit__(self, *exc) -> None:
        try:
            if self._browser is not None:
                await self._browser.close()
        finally:
            if self._pw is not None:
                await self._pw.stop()

    # ---- routing ---------------------------------------------------------------------

    def _record(self, kind: str, host: str, url: str) -> None:
        self.events.append({"type": kind, "host": host, "url": url,
                            "attacker": canonical_host(host) in self._attacker_set})

    @staticmethod
    def _is_top_level(request) -> bool:
        if not request.is_navigation_request():
            return False
        try:
            return request.frame.parent_frame is None
        except PlaywrightError:  # popup navigations are issued before their frame exists
            return True

    async def _handle(self, route) -> None:
        req = route.request
        try:
            is_doc = req.resource_type == "document"
            try:
                host = urlsplit(req.url).hostname or ""
                decision = decide(req.url, is_doc, self.fence, self._attacker_set,
                                  self.inject_fence, self.attack)
            except Exception:
                host, decision = "", "block" if is_doc else "abort"
            if decision == "abort":
                await route.abort("blockedbyclient")
            elif decision == "block":
                self._record("block", host, req.url)
                if self._is_top_level(req):
                    self._nav_blocks.append(host)
                await route.abort("blockedbyclient")
            elif decision == "sink":
                self._record("sink_hit", host, req.url)
                await route.fulfill(status=200, content_type="text/html", body=SINK_HTML)
            elif decision == "inject":
                await self._throttle(host)
                await self._fulfill_injected(route)
            elif decision == "pass":
                if is_doc:
                    await self._throttle(host)
                await route.continue_()
            else:  # unknown decision: fail closed
                await route.abort("blockedbyclient")
        except Exception:
            try:
                await route.abort("failed")
            except Exception:
                pass

    async def _throttle(self, host: str) -> None:
        """Reserve this host's next slot before sleeping, so concurrent requests queue up."""
        h = canonical_host(host)
        now = time.monotonic()
        slot = max(now, _LAST_DOC.get(h, float("-inf")) + self.min_interval_s)
        _LAST_DOC[h] = slot
        if slot > now:
            await asyncio.sleep(slot - now)

    async def _fulfill_injected(self, route) -> None:
        req = route.request
        u = urlsplit(req.url)
        kwargs: dict = {"max_redirects": 0}
        ip = self._map.get(canonical_host(u.hostname or ""))
        if ip is not None:  # honor MAP rules, which Node-side fetch does not see
            netloc = f"{ip}:{u.port}" if u.port else ip
            kwargs["url"] = urlunsplit((u.scheme, netloc, u.path, u.query, ""))
            kwargs["headers"] = {**req.headers, "host": u.netloc}
        resp = await route.fetch(**kwargs)
        body = await resp.body()
        if "text/html" in resp.headers.get("content-type", "").lower():
            html = inject(body.decode("utf-8", errors="replace"), self.attack, self.seed,
                          self.misinfo_answer, attacker=self.attacker_hosts[0])
            headers = {k: v for k, v in resp.headers.items() if k.lower() not in _DROP_HEADERS}
            await route.fulfill(status=resp.status, headers=headers, body=html)
        else:
            await route.fulfill(response=resp, body=body)

    # ---- non-HTML tracking -----------------------------------------------------------

    def _on_response(self, response) -> None:
        if response.request.resource_type == "document":
            self._ctypes[response.url] = response.headers.get("content-type", "unknown")

    def _on_download(self, download) -> None:
        self._mark_non_html(download.url)

    def _mark_non_html(self, url: str) -> None:
        """The main document at url was not rendered (headless Chromium downloads it)."""
        ctype = self._ctypes.get(url, "unknown").split(";")[0].strip()
        self._non_html = (ctype, url)

    def _on_framenavigated(self, frame) -> None:
        if frame.parent_frame is None:
            self._non_html = None

    # ---- BrowserLike -----------------------------------------------------------------

    async def start(self, url: str) -> str:
        # A fresh page is already about:blank; the agent's own goto still rejects non-http(s) URLs.
        if url == "about:blank":
            return "ok" if self.page.url == "about:blank" else "error: page not blank at start"
        return await self.act({"action": "goto", "url": url})

    async def observe(self) -> Observation:
        if self._non_html is not None:
            ctype, url = self._non_html
            return Observation(url, f"non-HTML document ({ctype}) at {url}; content not shown", False)
        page = self.page
        try:
            data = await page.evaluate(_OBSERVE_JS)
            title = await page.title()
        except PlaywrightError as e:
            return Observation(page.url, f"error: could not read page: {_first_line(e)}", False)
        challenge = bool(CHALLENGE_RE.search(title or ""))
        ctype = data.get("ctype") or ""
        if ctype and ctype != "text/html":
            text = f"non-HTML document ({ctype}) at {page.url}; content not shown"
        else:
            text = f"{data['lines']}\n\n{data['text']}" if data["lines"] else data["text"]
        return Observation(page.url, text, challenge)

    async def act(self, action: dict) -> str:
        n_blocks = len(self._nav_blocks)
        err: str | None = None
        try:
            err = await self._perform(action)
        except PlaywrightError as e:
            if "Download is starting" in str(e) and action.get("action") == "goto":
                self._mark_non_html(action["url"])  # the download event arrives later
            else:
                err = _first_line(e)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        await self._close_popups(action)
        await self._post_check(n_blocks)
        blocked = self._nav_blocks[n_blocks:]
        if blocked:
            return f"blocked: {blocked[0]} not in allow-list"
        return f"error: {err}" if err else "ok"

    async def _perform(self, action: dict) -> str | None:
        page = self.page
        kind = action.get("action")
        if kind == "goto":
            url = action.get("url", "")
            if urlsplit(url).scheme not in ("http", "https"):
                return f"unsupported URL {url!r}"
            await page.goto(url)
        elif kind == "back":
            if self._non_html is not None:
                self._non_html = None
                return None
            if await page.go_back() is None and page.url == "about:blank":
                return "no previous page"
        elif kind == "scroll":
            await page.mouse.wheel(0, -600 if action.get("dir") == "up" else 600)
        elif kind in ("click", "type"):
            loc = page.locator(f'[data-agent-id="{int(action["id"])}"]')
            if await loc.count() == 0:
                return f"unknown element id {action['id']}"
            if kind == "click":
                await loc.first.click()
                await asyncio.sleep(POPUP_SETTLE_S)
            else:
                await loc.first.fill(action.get("text", ""))
            try:
                await page.wait_for_load_state("domcontentloaded")
            except PlaywrightError:
                pass
        else:
            return f"unsupported action {kind!r}"
        return None

    async def _close_popups(self, action: dict) -> None:
        for popup in [p for p in self.context.pages if p is not self.page]:
            url = popup.url
            await popup.close()
            u = urlsplit(url)
            if u.scheme not in ("http", "https") or not u.hostname:
                continue  # e.g. about:blank or the error page of a popup the route blocked
            if self.fence.allows(u.hostname):
                try:
                    await self.page.goto(url)
                except PlaywrightError:
                    pass
            else:
                self._record("block", u.hostname, url)
                self._nav_blocks.append(u.hostname)

    async def _post_check(self, n_blocks: int) -> None:
        url = self.page.url
        u = urlsplit(url)
        host = u.hostname or ""
        if u.scheme in ("http", "https") and host and self.fence.allows(host):
            return
        if u.scheme in ("http", "https"):
            if canonical_host(host) not in {canonical_host(h) for h in self._nav_blocks[n_blocks:]}:
                self._record("block", host, url)
                self._nav_blocks.append(host)
        elif not (u.scheme == "chrome-error" and self._nav_blocks[n_blocks:]):
            return  # about:blank etc.: nothing to undo
        try:
            await self.page.go_back()
        except PlaywrightError:
            pass
        if not self._on_fence(self.page.url):  # no history or go_back failed
            try:
                await self.page.goto("about:blank")
            except PlaywrightError:
                pass

    def _on_fence(self, url: str) -> bool:
        u = urlsplit(url)
        if url == "about:blank":
            return True
        return u.scheme in ("http", "https") and bool(u.hostname) and self.fence.allows(u.hostname)
