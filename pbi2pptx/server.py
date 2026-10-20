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
from urllib.parse import quote, unquote

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import __version__, static_dir
from .export import Exporter, ExportRefused
from .page_url import Filter, parse_page_url
from .power_bi_window import CurrentPage, FilterCheck, NotAReportPage
from .selection import Entry, Selection, SelectionError
from .template import Box, NotATemplate, TemplateInfo, describe_template
from .window_service import Busy, WindowNotOpen, WindowService

TOKEN_HEADER = "X-PBI2PPTX-Token"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
FILE_NAME_HEADER = "X-File-Name"
MAX_TEMPLATE_BYTES = 100 * 1024 * 1024
EMU_PER_CM = 360_000
STATIC = static_dir()  # the built interface (ui/, `npm run build`)

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


def template_json(info: TemplateInfo) -> dict:
    """Layout geometry as fractions of the slide, so the interface can draw it at any size."""
    w, h = info.slide_width, info.slide_height

    def rel(box: Box | None) -> dict | None:
        if box is None:
            return None
        return {"x": box.left / w, "y": box.top / h, "w": box.width / w, "h": box.height / h}

    return {
        "fileName": info.file_name,
        "slideWidthCm": round(w / EMU_PER_CM, 1),
        "slideHeightCm": round(h / EMU_PER_CM, 1),
        "templateSlides": info.template_slides,
        "preselected": info.preselected,
        "layouts": [
            {
                "name": i.name,
                "usable": i.usable,
                "preselected": i.preselected,
                "imageArea": rel(i.image_area),
                "title": rel(i.title),
                "footers": [rel(b) for b in i.footers],
                "graphics": [{"name": name, **rel(box)} for name, box in i.graphics],
            }
            for i in info.layouts
        ],
    }


def create_app(
    service: WindowService,
    token: str,
    allowed_hosts: Iterable[str],
    on_quit: Callable[[], None] = lambda: None,
    on_started: Callable[[], None] = lambda: None,
    static_dir: Path = STATIC,
) -> Starlette:
    allowed = set(allowed_hosts)
    # The Template the User picked: in memory only, for the Export (ADR 0003: nothing stored).
    template: dict = {}
    exporter = Exporter(service)

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
        try:
            await service.sign_out()
        except Busy as e:
            return problem(409, str(e))
        return JSONResponse({"ok": True})

    def proposed_entry(current: CurrentPage) -> dict:
        return Entry(current.page_url.url, current.page_name, current.report_name, current.page_name).to_json()

    async def add_current_page(request: Request) -> Response:
        try:
            return JSONResponse({"entry": proposed_entry(await service.current_page())})
        except (WindowNotOpen, Busy) as e:
            return problem(409, str(e))
        except NotAReportPage:
            return problem(422, "The Power BI Window isn't showing a report page. Open the page you want there, then try again.")

    async def add_by_address(request: Request) -> Response:
        address = str((await json_body(request)).get("address", "")).strip()
        try:
            return JSONResponse({"entry": proposed_entry(await service.resolve(address))})
        except (WindowNotOpen, Busy) as e:
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

    async def get_template(request: Request) -> Response:
        return JSONResponse({"template": template_json(template["info"]) if template else None})

    async def put_template(request: Request) -> Response:
        if int(request.headers.get("content-length") or 0) > MAX_TEMPLATE_BYTES:
            return problem(413, "This file is too large for a template (more than 100 MB).")
        data = await request.body()
        if len(data) > MAX_TEMPLATE_BYTES:
            return problem(413, "This file is too large for a template (more than 100 MB).")
        name = unquote(request.headers.get(FILE_NAME_HEADER, "")).strip() or "Template.potx"
        try:
            info = describe_template(data, name)
        except NotATemplate as e:
            return problem(422, str(e))
        if not any(i.usable for i in info.layouts):
            return problem(422, "This template has no slide layout with a title, so there is nowhere to put the pages.")
        template.update(data=data, info=info)
        return JSONResponse({"template": template_json(info)})

    async def check_filter(request: Request) -> Response:
        body = await json_body(request)
        try:
            page_url = parse_page_url(str(body.get("pageUrl", "")))
            flt = Filter.from_json(body.get("filter") or {})
        except (ValueError, AttributeError):
            return problem(422, "A Filter check needs a page address and a complete Filter.")
        try:
            verdict = await service.check_filters(page_url, [flt])
        except (WindowNotOpen, Busy) as e:
            return problem(409, str(e))
        except NotAReportPage as e:
            return problem(422, str(e))
        messages = {
            FilterCheck.APPLIED: "Power BI applied it.",
            FilterCheck.NOT_APPLIED: f"Power BI didn't recognise {flt.table} / {flt.column}. Check the table and column names.",
            FilterCheck.NOT_VERIFIABLE: "Can't check: this report hides its filter pane.",
        }
        return JSONResponse({"result": verdict.check.value, "message": messages.get(verdict.check, "")})

    async def start_export(request: Request) -> Response:
        try:
            selection = Selection.from_json({**((await json_body(request)).get("selection") or {}), "schemaVersion": 1})
            exporter.start(selection, template.get("data"))
        except (SelectionError, ExportRefused) as e:
            return problem(409 if isinstance(e, ExportRefused) else 422, str(e))
        return JSONResponse({"ok": True}, status_code=202)

    async def export_progress(request: Request) -> Response:
        return JSONResponse({"export": exporter.progress.to_json(), "deckReady": exporter.deck() is not None})

    async def cancel_export(request: Request) -> Response:
        exporter.cancel()
        return JSONResponse({"ok": True})

    async def download_deck(request: Request) -> Response:
        deck = exporter.deck()
        if deck is None:
            return problem(404, "There is no Deck to download. Run an Export first.")
        file_name, data = deck
        fallback = file_name.encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
        disposition = f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(file_name)}"
        return Response(data, media_type=PPTX, headers={"Content-Disposition": disposition})

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
            await exporter.stop()
            await service.stop()

    app_state = {"template": template, "exporter": exporter}
    routes = [
        Route("/", index),
        Route("/api/status", api(status)),
        Route("/api/window/show", api(show_window), methods=["POST"]),
        Route("/api/sign-out", api(sign_out), methods=["POST"]),
        Route("/api/entries/current", api(add_current_page), methods=["POST"]),
        Route("/api/entries/resolve", api(add_by_address), methods=["POST"]),
        Route("/api/selection/open", api(open_selection), methods=["POST"]),
        Route("/api/selection/save", api(save_selection), methods=["POST"]),
        Route("/api/filters/check", api(check_filter), methods=["POST"]),
        Route("/api/export", api(export_progress)),
        Route("/api/export", api(start_export), methods=["POST"]),
        Route("/api/export/cancel", api(cancel_export), methods=["POST"]),
        Route("/api/export/deck", api(download_deck)),
        Route("/api/template", api(get_template)),
        Route("/api/template", api(put_template), methods=["POST"]),
        Route("/api/quit", api(quit_tool), methods=["POST"]),
    ]
    if (static_dir / "assets").is_dir():
        routes.append(Mount("/assets", StaticFiles(directory=static_dir / "assets")))
    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.session = app_state
    return app
