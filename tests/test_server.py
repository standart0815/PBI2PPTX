from starlette.testclient import TestClient

from pbi2pptx.page_url import parse_page_url
from pbi2pptx.power_bi_window import CurrentPage, NotAReportPage
from pbi2pptx.server import TOKEN_HEADER, create_app
from pbi2pptx.window_service import WindowNotOpen, WindowState, WindowStatus

TOKEN = "secret-token"
AUTH = {TOKEN_HEADER: TOKEN}
PAGE = "https://app.powerbi.com/groups/me/apps/a1a1a1a1-0000-0000-0000-000000000005/reports/11111111-0000-0000-0000-000000000001/aaaa0000000000000001?ctid=t-1"


class FakeService:
    def __init__(self):
        self.calls = []
        self.failure = None

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

    async def current_page(self):
        if self.failure:
            raise self.failure
        return CurrentPage(parse_page_url(PAGE), "Umsatz", "Beispielbericht")

    async def resolve(self, address):
        if self.failure:
            raise self.failure
        parse_page_url(address)  # like the real window: anything else is a ValueError
        return CurrentPage(parse_page_url(address), "Umsatz", "Beispielbericht")


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


def test_add_current_page_proposes_an_entry(tmp_path):
    app, _, _ = make(tmp_path)
    with TestClient(app) as client:
        entry = client.post("/api/entries/current", headers=AUTH).json()["entry"]
    assert entry == {"pageUrl": PAGE, "pageName": "Umsatz", "reportName": "Beispielbericht", "slideTitle": "Umsatz", "filters": []}


def test_adding_explains_what_to_do_when_it_cannot(tmp_path):
    app, service, _ = make(tmp_path)
    with TestClient(app) as client:
        service.failure = WindowNotOpen("The Power BI Window isn't open.")
        closed = client.post("/api/entries/current", headers=AUTH)
        service.failure = NotAReportPage("no canvas")
        elsewhere = client.post("/api/entries/current", headers=AUTH)
        service.failure = None
        nonsense = client.post("/api/entries/resolve", headers=AUTH, json={"address": "https://example.com"})
    assert (closed.status_code, closed.json()["error"]) == (409, "The Power BI Window isn't open.")
    assert elsewhere.status_code == 422 and "isn't showing a report page" in elsewhere.json()["error"]
    assert nonsense.status_code == 422 and "isn't the address of a Power BI report page" in nonsense.json()["error"]


def test_pasted_address_becomes_an_entry(tmp_path):
    app, _, _ = make(tmp_path)
    with TestClient(app) as client:
        entry = client.post("/api/entries/resolve", headers=AUTH, json={"address": PAGE}).json()["entry"]
    assert entry["pageUrl"] == PAGE


def test_save_and_open_a_selection(tmp_path):
    app, _, _ = make(tmp_path)
    selection = {
        "name": "Monthly pack: EMEA",
        "renderLanguage": "en-US",
        "slideLayout": None,
        "entries": [{"pageUrl": PAGE, "pageName": "Umsatz", "reportName": "Beispielbericht", "slideTitle": "DE", "filters": []}],
    }
    with TestClient(app) as client:
        saved = client.post("/api/selection/save", headers=AUTH, json={"selection": selection}).json()
        opened = client.post("/api/selection/open", headers=AUTH, json={"content": saved["content"]}).json()["selection"]
        broken = client.post("/api/selection/open", headers=AUTH, json={"content": "{"})
    assert saved["fileName"] == "Monthly pack EMEA.json"
    assert opened["entries"] == selection["entries"] and opened["renderLanguage"] == "en-US"
    assert broken.status_code == 422 and "not valid JSON" in broken.json()["error"]
