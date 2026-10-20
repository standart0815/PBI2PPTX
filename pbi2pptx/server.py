"""The local server: serves the interface and the API, on 127.0.0.1 only.

Every API call must carry the per-launch token (header X-PBI2PPTX-Token), and every request
must be addressed to 127.0.0.1 or localhost. Together these keep other websites open in the
User's browser from driving the tool, including via DNS rebinding.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
from pathlib import Path
from typing import Callable, Iterable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import __version__
from .power_bi_window import CurrentPage, NotAReportPage
from .selection import Entry, Selection, SelectionError
from .window_service import WindowNotOpen, WindowService

TOKEN_HEADER = "X-PBI2PPTX-Token"
STATIC = Path(__file__).parent / "static"  # the built interface (ui/, `npm run build`)

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>PBI2PPTX</title>
<body style="font-family:sans-serif;max-width:40rem;margin:3rem auto">
<h1>The interface isn't built yet</h1>
<p>Build it once, then reload this page:</p>
<pre>npm --prefix ui install
npm --prefix ui run build</pre></body>"""


def problem(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def json_body(request: Request) -> dict:
    try:
        data = await request.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def create_app(
    service: WindowService,
    token: str,
    allowed_hosts: Iterable[str],
    on_quit: Callable[[], None] = lambda: None,
    on_started: Callable[[], None] = lambda: None,
    static_dir: Path = STATIC,
) -> Starlette:
    allowed = set(allowed_hosts)

    def guard(request: Request, needs_token: bool) -> Response | None:
        if request.headers.get("host", "") not in allowed:
            return JSONResponse({"error": "wrong host"}, status_code=403)
        if needs_token and not secrets.compare_digest(request.headers.get(TOKEN_HEADER, ""), token):
            return JSONResponse({"error": "missing or wrong token"}, status_code=401)
        return None

    def api(handler):
        async def wrapped(request: Request) -> Response:
            return guard(request, needs_token=True) or await handler(request)

        return wrapped

    async def index(request: Request) -> Response:
        if refused := guard(request, needs_token=False):
            return refused
        if not secrets.compare_digest(request.query_params.get("token", ""), token):
            return HTMLResponse("<h1>Please start PBI2PPTX from its icon or command.</h1>", status_code=401)
        page = static_dir / "index.html"
        return FileResponse(page) if page.exists() else HTMLResponse(NOT_BUILT)

    async def status(request: Request) -> Response:
        window = await service.status()
        return JSONResponse({"version": __version__, "window": window.to_json()})

    async def show_window(request: Request) -> Response:
        await service.show()
        return JSONResponse({"ok": True})

    async def sign_out(request: Request) -> Response:
        await service.sign_out()
        return JSONResponse({"ok": True})

    def proposed_entry(current: CurrentPage) -> dict:
        return Entry(current.page_url.url, current.page_name, current.report_name, current.page_name).to_json()

    async def add_current_page(request: Request) -> Response:
        try:
            return JSONResponse({"entry": proposed_entry(await service.current_page())})
        except WindowNotOpen as e:
            return problem(409, str(e))
        except NotAReportPage:
            return problem(422, "The Power BI Window isn't showing a report page. Open the page you want there, then try again.")

    async def add_by_address(request: Request) -> Response:
        address = str((await json_body(request)).get("address", "")).strip()
        try:
            return JSONResponse({"entry": proposed_entry(await service.resolve(address))})
        except WindowNotOpen as e:
            return problem(409, str(e))
        except NotAReportPage as e:
            return problem(422, str(e))
        except ValueError:
            return problem(422, "That isn't the address of a Power BI report page or a shared Power BI App link.")

    async def open_selection(request: Request) -> Response:
        try:
            selection = Selection.loads(str((await json_body(request)).get("content", "")))
        except SelectionError as e:
            return problem(422, str(e))
        return JSONResponse({"selection": selection.to_json()})

    async def save_selection(request: Request) -> Response:
        data = (await json_body(request)).get("selection")
        try:
            selection = Selection.from_json({**(data or {}), "schemaVersion": 1})
        except SelectionError as e:
            return problem(422, str(e))
        return JSONResponse({"fileName": selection.file_name(), "content": selection.dumps()})

    async def quit_tool(request: Request) -> Response:
        on_quit()
        return JSONResponse({"ok": True})

    @contextlib.asynccontextmanager
    async def lifespan(app):
        on_started()  # open the interface first, so the User sees "starting…" right away
        opening = asyncio.create_task(service.start())
        try:
            yield
        finally:
            opening.cancel()
            with contextlib.suppress(BaseException):
                await opening
            await service.stop()

    routes = [
        Route("/", index),
        Route("/api/status", api(status)),
        Route("/api/window/show", api(show_window), methods=["POST"]),
        Route("/api/sign-out", api(sign_out), methods=["POST"]),
        Route("/api/entries/current", api(add_current_page), methods=["POST"]),
        Route("/api/entries/resolve", api(add_by_address), methods=["POST"]),
        Route("/api/selection/open", api(open_selection), methods=["POST"]),
        Route("/api/selection/save", api(save_selection), methods=["POST"]),
        Route("/api/quit", api(quit_tool), methods=["POST"]),
    ]
    if (static_dir / "assets").is_dir():
        routes.append(Mount("/assets", StaticFiles(directory=static_dir / "assets")))
    return Starlette(routes=routes, lifespan=lifespan)
