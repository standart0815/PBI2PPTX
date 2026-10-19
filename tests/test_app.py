"""Starting: one instance at a time, and its note on disk."""

import json
import threading
import time
import urllib.request

import pytest

from pbi2pptx import app


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "data_dir", lambda: tmp_path)
    return tmp_path


def test_no_note_means_no_running_instance(data_dir):
    assert app._running_instance() is None


def test_a_stale_note_is_ignored(data_dir):
    (data_dir / "instance.json").write_text(json.dumps({"port": app._free_port(), "token": "x", "pid": 1}))
    assert app._running_instance() is None


def test_a_second_start_opens_the_running_interface(data_dir, monkeypatch):
    # A stand-in for a running PBI2PPTX that answers its status call.
    from http.server import BaseHTTPRequestHandler
    from socketserver import TCPServer  # not HTTPServer: it resolves the host name, which can take half a minute

    class Status(BaseHTTPRequestHandler):
        def do_GET(self):
            ok = self.headers.get(app.TOKEN_HEADER) == "secret"
            self.send_response(200 if ok else 401)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = TCPServer(("127.0.0.1", 0), Status)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        app._write_instance_file(port, "secret")
        opened = []
        monkeypatch.setattr(app.webbrowser, "open", opened.append)
        app.main([])  # returns right away instead of starting a second server
        assert opened == [f"http://127.0.0.1:{port}/?token=secret"]
    finally:
        server.shutdown()


def test_the_note_is_only_removed_by_its_own_instance(data_dir):
    app._write_instance_file(1234, "mine")
    app._remove_instance_file("someone else's")
    assert (data_dir / "instance.json").exists()
    app._remove_instance_file("mine")
    assert not (data_dir / "instance.json").exists()


def test_tray_icon_image_is_a_square_with_transparency():
    from pbi2pptx.tray import icon_image

    img = icon_image(64)
    assert (img.size, img.mode) == ((64, 64), "RGBA")
    assert img.getpixel((0, 0))[3] == 0  # transparent corner
    assert img.getpixel((32, 10)) == (31, 95, 191, 255)  # blue tile


def test_quitting_from_the_icon_stops_the_server_and_the_icon(monkeypatch, caplog):
    """The icon's life follows the server thread: quit from either side ends both."""
    import sys
    import types

    events = []

    class FakeIcon:
        def __init__(self, name, image, title, menu):
            self.menu, self.visible = menu, False

        def run(self, setup):
            events.append("icon shown")
            # The User picks "Quit PBI2PPTX" in the menu…
            quit_item = [item for item in self.menu if getattr(item, "text", "") == "Quit PBI2PPTX"][0]
            threading.Thread(target=setup, args=(self,)).start()
            time.sleep(0.1)
            quit_item(self)
            while "icon stopped" not in events:
                time.sleep(0.05)

        def stop(self):
            events.append("icon stopped")

    fake = types.SimpleNamespace(
        Icon=FakeIcon,
        Menu=type("Menu", (list,), {"__init__": lambda self, *items: list.__init__(self, items), "SEPARATOR": None}),
        MenuItem=type("MenuItem", (), {
            "__init__": lambda self, text, action, default=False: setattr(self, "text", text) or setattr(self, "action", action),
            "__call__": lambda self, icon: self.action(),
        }),
    )
    monkeypatch.setitem(sys.modules, "pystray", fake)

    stop = threading.Event()
    server_thread = threading.Thread(target=stop.wait)
    server_thread.start()

    from pbi2pptx import tray

    with caplog.at_level("INFO", logger="pbi2pptx"):
        tray.run(on_open=lambda: None, on_quit=lambda: (events.append("quit"), stop.set()), server_thread=server_thread)
    assert events == ["icon shown", "quit", "icon stopped"]
    assert "Quit from the menu bar icon" in caplog.text  # tells a menu Quit from one in the interface


def test_self_test_passes_from_source(capsys):
    from pbi2pptx.self_test import run

    assert run() == 0, capsys.readouterr().err
