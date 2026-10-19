"""Starting PBI2PPTX: `uv run pbi2pptx` (later: the installer's app icon)."""

from __future__ import annotations

import argparse
import secrets
import socket
import threading
import webbrowser

import uvicorn

from . import __version__
from .server import create_app
from .window_service import WindowService


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="pbi2pptx", description="Turn Power BI report pages into one PowerPoint deck.")
    parser.add_argument("--port", type=int, default=0, help="port for the local interface (default: any free port)")
    parser.add_argument("--no-open", action="store_true", help="don't open the interface in the default browser")
    parser.add_argument("--version", action="version", version=f"PBI2PPTX {__version__}")
    args = parser.parse_args(argv)

    port = args.port or _free_port()
    token = secrets.token_urlsafe(24)
    url = f"http://127.0.0.1:{port}/?token={token}"
    server: uvicorn.Server | None = None

    def quit_tool() -> None:
        server.should_exit = True

    def interface_ready() -> None:
        print(f"PBI2PPTX {__version__} is running. Interface: {url}", flush=True)
        print("Quit from the interface, or press Ctrl+C here.", flush=True)
        if not args.no_open:
            threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    app = create_app(
        WindowService(),
        token,
        allowed_hosts={f"127.0.0.1:{port}", f"localhost:{port}"},
        on_quit=quit_tool,
        on_started=interface_ready,
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    server.run()


if __name__ == "__main__":
    main()
