"""Local aiohttp app serving fake hosts (seed.test, partner.test, attacker) by Host header."""
from __future__ import annotations

from aiohttp import web

PDF_BYTES = b"%PDF-1.4\n% DomainFence fixture\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"
ATTACKER = "seed-info-portal.com"


def _page(title: str, body: str) -> web.Response:
    return web.Response(
        text=f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>",
        content_type="text/html",
    )


async def _handle(request: web.Request) -> web.StreamResponse:
    host, _, port = request.host.partition(":")
    host = host.lower()
    path = request.path
    if host == "seed.test":
        if path == "/":
            return _page("Seed University", (
                "<h1>Seed University</h1><p>Tuition is $50,000 per year.</p>"
                '<a href="/info">Info</a> <a href="/redirect">Redirect</a> '
                '<a href="/doc.pdf">Calendar PDF</a> '
                f'<a href="http://partner.test:{port}/" target="_blank">Partner</a>'
            ))
        if path == "/info":
            return _page("Info", "<p>Information page.</p>")
        if path == "/redirect":
            raise web.HTTPFound(f"http://{ATTACKER}:{port}/verify")
        if path == "/doc.pdf":
            return web.Response(body=PDF_BYTES, content_type="application/pdf")
    elif host == "partner.test" and path == "/":
        return _page("Partner", "<p>partner page</p>")
    elif host == ATTACKER and path == "/verify":
        return _page("Portal", "<p>attacker portal</p>")
    raise web.HTTPNotFound()


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", _handle)
    return app


async def start_server() -> tuple[web.AppRunner, int]:
    """Start the app on 127.0.0.1 at a free port; returns (runner, port)."""
    runner = web.AppRunner(make_app())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port
