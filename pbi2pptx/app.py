"""Starting PBI2PPTX: the installed app's icon, or `uv run pbi2pptx` while developing."""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import secrets
import socket
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from . import __version__
from .power_bi_window import profile_dir
from .server import TOKEN_HEADER, create_app
from .window_service import WindowService

log = logging.getLogger("pbi2pptx")


def data_dir() -> Path:
    """Where the tool keeps its few files: the browser profile, the log, the running-instance note."""
    return profile_dir().parent


def _setup_logging() -> Path:
    """Log what the tool does (never report content) to a small rotating file, and to the terminal if any."""
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    log_file = folder / "pbi2pptx.log"
    handlers: list[logging.Handler] = [logging.handlers.RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=2, encoding="utf-8")]
    if sys.stderr is not None and not getattr(sys, "frozen", False):
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers, force=True)
    if getattr(sys, "frozen", False):
        # An app started from the Dock or Start menu has no terminal: keep stray output in the log.
        stream = open(log_file, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - lives as long as the process
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
    return log_file


def _instance_file() -> Path:
    return data_dir() / "instance.json"


def _running_instance() -> str | None:
    """The interface address of a PBI2PPTX that is already running, if any."""
    try:
        data = json.loads(_instance_file().read_text(encoding="utf-8"))
        port, token = int(data["port"]), str(data["token"])
        request = urllib.request.Request(f"http://127.0.0.1:{port}/api/status", headers={TOKEN_HEADER: token})
        with urllib.request.urlopen(request, timeout=2) as response:
            if response.status == 200:
                return f"http://127.0.0.1:{port}/?token={token}"
    except Exception:  # noqa: BLE001 - no note, stale note, or not answering: start a new one
        pass
    return None


def _write_instance_file(port: int, token: str) -> None:
    path = _instance_file()
    path.write_text(json.dumps({"port": port, "token": token, "pid": os.getpid()}), encoding="utf-8")
    path.chmod(0o600)


def _remove_instance_file(token: str) -> None:
    try:
        if json.loads(_instance_file().read_text(encoding="utf-8")).get("token") == token:
            _instance_file().unlink()
    except Exception:  # noqa: BLE001
        pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="pbi2pptx", description="Turn Power BI report pages into one PowerPoint deck.")
    parser.add_argument("--port", type=int, default=0, help="port for the local interface (default: any free port)")
    parser.add_argument("--no-open", action="store_true", help="don't open the interface in the default browser")
    parser.add_argument(
        "--tray",
        action=argparse.BooleanOptionalAction,
        default=getattr(sys, "frozen", False),
        help="show the menu bar / tray icon (default: on in the installed app, off when started from a terminal)",
    )
    parser.add_argument("--version", action="version", version=f"PBI2PPTX {__version__}")
    parser.add_argument("--self-test", action="store_true", help="check the installation offline, then exit")
    args = parser.parse_args(argv)
    log_file = _setup_logging()
    if args.self_test:
        from .self_test import run as self_test

        sys.exit(self_test())

    # Only one PBI2PPTX at a time: the Power BI Window's profile can't be shared.
    existing = _running_instance()
    if existing:
        log.info("PBI2PPTX is already running; opening its interface")
        print(f"PBI2PPTX is already running. Interface: {existing}", flush=True)
        if not args.no_open:
            webbrowser.open(existing)
        return

    port = args.port or _free_port()
    token = secrets.token_urlsafe(24)
    url = f"http://127.0.0.1:{port}/?token={token}"
    server: uvicorn.Server | None = None

    def quit_tool() -> None:
        log.info("Quit from the interface")
        server.should_exit = True

    def interface_ready() -> None:
        log.info("PBI2PPTX %s started on port %s (log: %s)", __version__, port, log_file)
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
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", log_config=None))
    _write_instance_file(port, token)
    try:
        if args.tray:
            _run_with_tray(server, url, quit_tool)
        else:
            server.run()
    finally:
        _remove_instance_file(token)
        log.info("PBI2PPTX stopped")


def _run_with_tray(server: uvicorn.Server, url: str, quit_tool) -> None:
    """The server in its own thread, the menu bar / tray icon on the main thread (macOS requires it)."""
    from . import tray

    thread = threading.Thread(target=server.run, name="server")
    thread.start()
    try:
        tray.run(on_open=lambda: webbrowser.open(url), on_quit=quit_tool, server_thread=thread)
    except Exception:  # noqa: BLE001 - no desktop session or no tray support: run without the icon
        log.exception("No menu bar / tray icon; quit from the interface")
    thread.join()


if __name__ == "__main__":
    main()
