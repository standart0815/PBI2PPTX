from starlette.testclient import TestClient

import contextlib
import time

from PIL import Image

from pbi2pptx.page_url import parse_page_url
from pbi2pptx.power_bi_window import CaptureReport, CurrentPage, FilterCheck, FilterVerdict, NotAReportPage
from pbi2pptx.server import TOKEN_HEADER, create_app
from pbi2pptx.window_service import Busy, WindowNotOpen, WindowState, WindowStatus

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

    async def current_page(self, include_filters=False):
        if self.failure:
            raise self.failure
        taken = None
        if include_filters:
            from pbi2pptx.page_url import Filter
            from pbi2pptx.set_filters import LeftOut, TakeOver

            taken = TakeOver([Filter("financials", "Country", ("Germany",))], [LeftOut("Slicer Date", "ranges aren't supported")])
        return CurrentPage(parse_page_url(PAGE), "Umsatz", "Beispielbericht"), taken

    async def check_filters(self, page_url, filters):
        if self.failure:
            raise self.failure
        applied = filters[0].table == "financials"
        return FilterVerdict(FilterCheck.APPLIED if applied else FilterCheck.NOT_APPLIED, () if applied else tuple(filters))

    @contextlib.asynccontextmanager
    async def exclusive(self, language):
        self.calls.append(f"export in {language}")
        yield FakeWindow()

    async def resolve(self, address):
        if self.failure:
            raise self.failure
        parse_page_url(address)  # like the real window: anything else is a ValueError
        return CurrentPage(parse_page_url(address), "Umsatz", "Beispielbericht")


class FakeWindow:
    def is_signed_in(self):
        return True

    async def capture(self, page_url, filters, out):
        Image.new("RGB", (1280, 720), "white").save(out)
        return CaptureReport(filters=FilterCheck.APPLIED if filters else FilterCheck.NO_FILTERS)


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


def upload(client, data: bytes, name="Firmen Vorlage.potx"):
    from urllib.parse import quote

    from pbi2pptx.server import FILE_NAME_HEADER

    return client.post("/api/template", headers={**AUTH, FILE_NAME_HEADER: quote(name)}, content=data)


def test_upload_a_template_and_read_it_back(tmp_path, sample_template):
    app, _, _ = make(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/template", headers=AUTH).json() == {"template": None}
        info = upload(client, sample_template.read_bytes()).json()["template"]
        again = client.get("/api/template", headers=AUTH).json()["template"]
    assert info == again
    assert (info["fileName"], info["slideWidthCm"], info["templateSlides"], info["preselected"]) == ("Firmen Vorlage.potx", 33.9, 1, "PBI Page")
    page = next(l for l in info["layouts"] if l["name"] == "PBI Page")
    area = page["imageArea"]
    assert area["x"] == 0 and area["w"] == 1  # full slide width
    assert 0 < area["y"] < area["y"] + area["h"] < 1
    assert app.state.session["template"]["data"] == sample_template.read_bytes()  # kept for the Export


def test_refuses_what_is_not_a_template(tmp_path):
    app, _, _ = make(tmp_path)
    with TestClient(app) as client:
        refused = upload(client, b"%PDF-1.7 not a template", "report.pdf")
        too_big = client.post("/api/template", headers={**AUTH, "content-length": str(200 * 1024 * 1024)}, content=b"x")
        still_none = client.get("/api/template", headers=AUTH).json()
    assert refused.status_code == 422 and "isn't a PowerPoint template" in refused.json()["error"]
    assert too_big.status_code == 413
    assert still_none == {"template": None}


def test_filter_check_answers_in_plain_words(tmp_path):
    app, service, _ = make(tmp_path)
    good = {"table": "financials", "column": "Country", "values": ["Germany"]}
    typo = {"table": "financial", "column": "Country", "values": ["Germany"]}
    with TestClient(app) as client:
        ok = client.post("/api/filters/check", headers=AUTH, json={"pageUrl": PAGE, "filter": good}).json()
        wrong = client.post("/api/filters/check", headers=AUTH, json={"pageUrl": PAGE, "filter": typo}).json()
        incomplete = client.post("/api/filters/check", headers=AUTH, json={"pageUrl": PAGE, "filter": {"table": "x"}})
        service.failure = Busy("An Export is running. Wait until it has finished.")
        busy = client.post("/api/filters/check", headers=AUTH, json={"pageUrl": PAGE, "filter": good})
    assert ok == {"result": "applied", "message": "Power BI applied it."}
    assert wrong["result"] == "not applied" and "didn't recognise financial / Country" in wrong["message"]
    assert incomplete.status_code == 422
    assert busy.status_code == 409 and "Export is running" in busy.json()["error"]


def test_export_runs_and_the_deck_downloads(tmp_path, sample_template):
    app, service, _ = make(tmp_path)
    selection = {
        "name": "Monthly pack: EMEA",
        "renderLanguage": "en-US",
        "slideLayout": "PBI Page",
        "entries": [
            {"pageUrl": PAGE, "pageName": "Umsatz", "reportName": "Beispielbericht", "slideTitle": "One", "filters": []},
            {"pageUrl": PAGE, "pageName": "Umsatz", "reportName": "Beispielbericht", "slideTitle": "Two",
             "filters": [{"table": "financials", "column": "Country", "values": ["Germany"]}]},
        ],
    }
    with TestClient(app) as client:
        assert client.get("/api/export/deck", headers=AUTH).status_code == 404
        no_template = client.post("/api/export", headers=AUTH, json={"selection": selection})
        upload(client, sample_template.read_bytes())
        assert client.post("/api/export", headers=AUTH, json={"selection": selection}).status_code == 202
        for _ in range(100):
            status = client.get("/api/export", headers=AUTH).json()
            if status["export"]["state"] != "running":
                break
            time.sleep(0.1)
        deck = client.get("/api/export/deck", headers=AUTH)
    assert no_template.status_code == 409 and "template" in no_template.json()["error"]
    assert status["export"]["state"] == "done" and status["deckReady"]
    assert [e["state"] for e in status["export"]["entries"]] == ["captured", "captured"]
    assert deck.status_code == 200 and deck.content[:2] == b"PK"
    assert "filename*=UTF-8''Monthly%20pack%20EMEA%20" in deck.headers["content-disposition"]
    assert "export in en-US" in service.calls


def test_add_current_page_can_take_over_the_set_filters(tmp_path):
    app, _, _ = make(tmp_path)
    with TestClient(app) as client:
        plain = client.post("/api/entries/current", headers=AUTH, json={}).json()
        with_filters = client.post("/api/entries/current", headers=AUTH, json={"includeFilters": True}).json()
    assert plain["entry"]["filters"] == [] and plain["leftOut"] == []
    assert with_filters["entry"]["filters"] == [{"table": "financials", "column": "Country", "values": ["Germany"]}]
    assert with_filters["leftOut"] == [{"what": "Slicer Date", "reason": "ranges aren't supported"}]
