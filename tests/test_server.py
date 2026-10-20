from starlette.testclient import TestClient

from pbi2pptx.server import TOKEN_HEADER, create_app
from pbi2pptx.window_service import WindowState, WindowStatus

TOKEN = "secret-token"


class FakeService:
    def __init__(self):
        self.calls = []

    async def start(self):
        self.calls.append("start")

    async def stop(self):
        self.calls.append("stop")

    async def status(self):
        return WindowStatus(WindowState.OPEN, signed_in=True, browser="chrome")

    async def show(self):
        self.calls.append("show")

    async def sign_out(self):
        self.calls.append("sign_out")


def make(tmp_path, built=False):
    static = tmp_path / "static"
    if built:
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text("<h1>interface</h1>")
        (static / "assets" / "app.js").write_text("console.log('ok')")
    service, events = FakeService(), []
    app = create_app(
        service,
        TOKEN,
        allowed_hosts={"testserver"},
        on_quit=lambda: events.append("quit"),
        on_started=lambda: events.append("started"),
        static_dir=static,
    )
    return app, service, events


def test_interface_needs_the_token(tmp_path):
    app, _, _ = make(tmp_path, built=True)
    with TestClient(app) as client:
        assert client.get("/").status_code == 401
        assert client.get("/?token=wrong").status_code == 401
        page = client.get(f"/?token={TOKEN}")
        assert page.status_code == 200 and "interface" in page.text
        assert client.get("/assets/app.js").status_code == 200


def test_explains_how_to_build_a_missing_interface(tmp_path):
    app, _, _ = make(tmp_path, built=False)
    with TestClient(app) as client:
        assert "npm --prefix ui run build" in client.get(f"/?token={TOKEN}").text


def test_api_needs_the_token(tmp_path):
    app, _, _ = make(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/status").status_code == 401
        assert client.get("/api/status", headers={TOKEN_HEADER: "wrong"}).status_code == 401
        assert client.post("/api/sign-out").status_code == 401


def test_refuses_requests_for_other_hosts(tmp_path):
    # A foreign website renamed to resolve to 127.0.0.1 (DNS rebinding) still sends its own host name.
    app, _, _ = make(tmp_path)
    with TestClient(app) as client:
        headers = {TOKEN_HEADER: TOKEN, "host": "evil.example:8000"}
        assert client.get("/api/status", headers=headers).status_code == 403


def test_status_reports_the_window(tmp_path):
    app, _, _ = make(tmp_path)
    with TestClient(app) as client:
        data = client.get("/api/status", headers={TOKEN_HEADER: TOKEN}).json()
    assert data["window"] == {"state": "open", "signed_in": True, "browser": "chrome", "message": ""}
    assert data["version"]


def test_actions_reach_the_window_service_and_quit(tmp_path):
    app, service, events = make(tmp_path)
    with TestClient(app) as client:
        for path in ("/api/window/show", "/api/sign-out", "/api/quit"):
            assert client.post(path, headers={TOKEN_HEADER: TOKEN}).json() == {"ok": True}
    assert service.calls == ["start", "show", "sign_out", "stop"]
    assert events == ["started", "quit"]
