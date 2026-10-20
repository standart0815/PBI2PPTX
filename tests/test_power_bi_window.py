"""Offline tests of the Power BI Window against tests/fixtures/fake_power_bi.html.

The fake page is served under the real https://app.powerbi.com/ address, so the code under
test runs unchanged. The browser is Playwright's bundled Chromium, headless, with a temporary
profile (install it once with `uv run playwright install chromium`).
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from pbi2pptx.page_url import DateFilter, Filter, ReachedThrough, parse_page_url
from pbi2pptx.power_bi_window import FilterCheck, FiltersNotApplied, NotAReportPage, PowerBIWindow

FAKE = (Path(__file__).parent / "fixtures" / "fake_power_bi.html").read_text(encoding="utf-8")
REPORT = "11111111-0000-0000-0000-000000000001"
WS_PAGE = f"https://app.powerbi.com/groups/2b2b2b2b-0000-0000-0000-000000000002/reports/{REPORT}/aaaa0000000000000001"
APP_LINK = "https://app.powerbi.com/Redirect?action=OpenApp&appId=a1a1a1a1-0000-0000-0000-000000000005&ctid=t-1"
MISSING = f"https://app.powerbi.com/groups/me/reports/00000000-0000-0000-0000-000000000000/aaaa0000000000000001"

TOOLBAR_RED = (255, 0, 0)
TIP_GREEN = (15, 107, 92)
PERSONAL_YELLOW = (255, 192, 0)


async def _serve_fake(route):
    if route.request.resource_type == "document":
        await route.fulfill(body=FAKE, content_type="text/html; charset=utf-8")
    else:
        await route.fulfill(status=204)


@asynccontextmanager
async def fake_window(tmp_path, language="de-DE"):
    window = PowerBIWindow(
        language=language, profile=tmp_path / "profile", browsers=(None,), headless=True, settle_ms=100, overlay_wait_ms=600
    )
    async with window:
        await window.context.route("https://app.powerbi.com/**", _serve_fake)
        yield window


def run(coro):
    return asyncio.run(coro)


def colors(path: Path) -> set:
    with Image.open(path) as img:
        return {c for _, c in img.convert("RGB").getcolors(maxcolors=1 << 22)}


def same_image(a: Path, b: Path) -> bool:
    with Image.open(a) as ia, Image.open(b) as ib:
        return ImageChops.difference(ia.convert("RGB"), ib.convert("RGB")).getbbox() is None


def test_tells_signed_in_from_signed_out(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            await w.open_home()
            signed_in = w.is_signed_in()
            await w.page.goto("https://app.powerbi.com/singleSignOn")
            return signed_in, w.is_signed_in()

    assert run(check()) == (True, False)


def test_current_page_reads_the_page_name_not_the_ribbon(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            await w.page.goto(WS_PAGE)
            return await w.current_page()

    current = run(check())
    assert current.page_name == "Umsatz"  # the ribbon's selected tab "Start" must not win
    assert current.report_name == "Beispielbericht"
    assert current.page_url.reached_through is ReachedThrough.WORKSPACE


def test_shared_app_link_resolves_to_an_app_page(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            return await w.resolve(APP_LINK)

    current = run(check())
    assert current.page_url.reached_through is ReachedThrough.POWER_BI_APP
    assert current.page_url.ctid == "t-1"
    assert current.page_name == "Umsatz"  # read from the App's own navigation
    assert current.report_name == "Beispielbericht"


def test_missing_report_is_not_a_report_page(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            await w.resolve(MISSING)

    with pytest.raises(NotAReportPage):
        run(check())


def test_rejects_addresses_that_are_neither_page_urls_nor_app_links(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            await w.resolve("https://app.powerbi.com/groups/me/list")

    with pytest.raises(ValueError):
        run(check())


def test_entry_links_open_the_page_as_the_user_sees_it(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            await w.show_page(parse_page_url(WS_PAGE + "?ctid=t-1"))
            plain = w.page.url
            await w.show_page(parse_page_url(WS_PAGE), [Filter("financials", "Country", ("Germany",))])
            return plain, w.page.url

    plain, filtered = run(check())
    assert plain == WS_PAGE + "?ctid=t-1"
    assert "filter=" in filtered and "financials/Country" in filtered.replace("%2F", "/")


def test_capture_is_the_clean_canvas(tmp_path):
    out = tmp_path / "page.png"

    async def check():
        async with fake_window(tmp_path) as w:
            return await w.capture(parse_page_url(WS_PAGE), [], out)

    report = run(check())
    assert (report.reset, report.fit_to_page, report.notes) == ("not needed", "already set", [])
    with Image.open(out) as img:
        assert img.size == (2560, 1440)  # the 1280×720 canvas at 2× pixel density
    found = colors(out)
    assert TOOLBAR_RED not in found  # hover toolbar hidden
    assert TIP_GREEN not in found  # the tip that appears after loading was dismissed


def test_capture_resets_personal_changes_to_the_default_state(tmp_path):
    default, changed = tmp_path / "default.png", tmp_path / "changed.png"

    async def check():
        async with fake_window(tmp_path) as w:
            await w.capture(parse_page_url(WS_PAGE), [], default)
            await w.page.evaluate("() => localStorage.setItem('fake-changed', '1')")
            return await w.capture(parse_page_url(WS_PAGE), [], changed)

    report = run(check())
    assert report.reset == "confirmed"
    assert PERSONAL_YELLOW not in colors(changed)
    assert same_image(default, changed)


def test_filters_change_the_capture_and_survive_the_reset(tmp_path):
    plain, filtered = tmp_path / "plain.png", tmp_path / "filtered.png"

    async def check():
        async with fake_window(tmp_path) as w:
            await w.capture(parse_page_url(WS_PAGE), [], plain)
            await w.page.evaluate("() => localStorage.setItem('fake-changed', '1')")
            report = await w.capture(parse_page_url(WS_PAGE), [Filter.parse("financials/Country=Germany")], filtered)
            return report, w.page.url

    report, url = run(check())
    assert report.reset == "confirmed"
    assert "filter=financials%2FCountry%20eq%20%27Germany%27" in url
    assert not same_image(plain, filtered)


def test_switches_to_fit_to_page_when_needed(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            await w.open_home()
            await w.page.evaluate("() => localStorage.setItem('fake-actual-size', '1')")
            return await w.capture(parse_page_url(WS_PAGE), [], tmp_path / "page.png")

    assert run(check()).fit_to_page == "set"


def test_app_page_capture_works_like_a_workspace_page(tmp_path):
    out = tmp_path / "app.png"

    async def check():
        async with fake_window(tmp_path) as w:
            current = await w.resolve(APP_LINK)
            return await w.capture(current.page_url, [Filter.parse("financials/Country=Germany")], out)

    report = run(check())
    assert report.notes == []
    assert TOOLBAR_RED not in colors(out)


def test_report_name_falls_back_to_the_title_without_the_page_name(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            await w.page.goto(WS_PAGE)
            await w.page.evaluate("() => document.querySelector('button.info-bar').remove()")
            return await w.current_page()

    assert run(check()).report_name == "Beispielbericht"  # from "Umsatz - Beispielbericht – Power BI"


def test_applied_filters_are_verified_and_the_pane_is_closed_again(tmp_path):
    out = tmp_path / "page.png"

    async def check():
        async with fake_window(tmp_path) as w:
            report = await w.capture(parse_page_url(WS_PAGE), [Filter.parse("financials/Country=Germany,France")], out)
            return report, await w.page.locator("filter-pane-modern").count()

    report, pane_left_open = run(check())
    assert report.filters is FilterCheck.APPLIED
    assert pane_left_open == 0
    with Image.open(out) as img:
        assert img.size == (2560, 1440)  # the full-width canvas, not the one narrowed by the open pane


def test_a_filter_power_bi_ignored_stops_the_capture(tmp_path):
    good, wrong = Filter.parse("financials/Segment=Government"), Filter.parse("financials/Land=Germany")

    async def check():
        async with fake_window(tmp_path) as w:
            await w.capture(parse_page_url(WS_PAGE), [good, wrong], tmp_path / "page.png")

    with pytest.raises(FiltersNotApplied) as raised:
        run(check())
    assert raised.value.missing == (wrong,)
    assert not (tmp_path / "page.png").exists()  # no misleading Page Image


def test_hidden_filter_pane_means_not_verifiable(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            await w.open_home()
            await w.page.evaluate("() => localStorage.setItem('fake-no-pane', '1')")
            return await w.capture(parse_page_url(WS_PAGE), [Filter.parse("financials/Country=Germany")], tmp_path / "page.png")

    report = run(check())
    assert report.filters is FilterCheck.NOT_VERIFIABLE
    assert (tmp_path / "page.png").exists()


def test_check_button_verifies_without_capturing(tmp_path):
    async def check():
        async with fake_window(tmp_path) as w:
            ok = await w.check_filters(parse_page_url(WS_PAGE), [Filter.parse("financials/Country=Germany")])
            typo = await w.check_filters(parse_page_url(WS_PAGE), [Filter.parse("financial/Country=Germany")])
            return ok, typo

    ok, typo = run(check())
    assert ok.check is FilterCheck.APPLIED
    assert typo.check is FilterCheck.NOT_APPLIED and typo.missing == (Filter.parse("financial/Country=Germany"),)


def test_reads_the_filters_a_user_set(tmp_path):
    import json

    pane = [{"table": "financials", "column": "Country", "condition": "ist Germany oder France"}]
    slicers = [
        {"column": "Discount Band", "kind": "list", "selectAll": "mixed", "items": [["High", False], ["Low", True], ["Medium", True]]},
        {"column": "Product", "kind": "dropdown", "text": "Alle"},
        {"column": "Date", "kind": "range", "available": ["01.01.2013", "31.12.2014"], "selected": ["01.06.2013", "31.12.2013"]},
        {"column": "Region", "kind": "list", "selectAll": "mixed", "items": [["EMEA", True], ["APAC", False]]},
        {"column": "Order Date", "kind": "other"},
    ]

    async def check():
        async with fake_window(tmp_path) as w:
            await w.open_home()
            await w.page.evaluate(
                "([p, s]) => { localStorage.setItem('fake-pane-filters', p); localStorage.setItem('fake-slicers', s); }",
                [json.dumps(pane), json.dumps(slicers)],
            )
            await w.page.goto(parse_page_url(WS_PAGE).with_filters([Filter.parse("financials/Segment=Government")]))
            await w._wait_until_rendered()
            result = await w.read_set_filters()
            return result, await w.page.locator("filter-pane-modern").count()

    result, pane_left_open = run(check())
    assert result.filters == [
        Filter("financials", "Segment", ("Government",)),  # the page address's own Filter shows as a card too
        Filter("financials", "Country", ("Germany", "France")),
        Filter("financials", "Discount Band", ("Low", "Medium")),  # table from the "Discount Band" card
        DateFilter("Calendar", "Date", date(2013, 6, 1), date(2013, 12, 31)),  # the date slicer, table from the "Date" card
    ]
    assert {lo.what: lo.reason for lo in result.left_out} == {
        "Slicer Region = EMEA": "table unknown: add this Filter by hand",
        "Slicer Order Date": "this kind of slicer isn't supported (such as relative dates)",
    }
    assert pane_left_open == 0


def test_a_shortened_card_is_opened_and_read(tmp_path):
    import json

    pane = [{"table": "financials", "column": "Country", "condition": "ist Germany, France und 1 weitere", "ticked": ["Germany", "France", "Mexico"]}]

    async def check():
        async with fake_window(tmp_path) as w:
            await w.open_home()
            await w.page.evaluate("p => localStorage.setItem('fake-pane-filters', p)", json.dumps(pane))
            await w.page.goto(WS_PAGE)
            await w._wait_until_rendered()
            return await w.read_set_filters()

    assert run(check()).filters == [Filter("financials", "Country", ("Germany", "France", "Mexico"))]


@pytest.mark.parametrize("language", ["de-DE", "en-US"])
def test_date_filters_are_verified_by_a_card_for_each_end(tmp_path, language):
    # Power BI shows "ist am oder nach 01.06.2013" and "ist vor 01.01.2014" ("is on or after 6/1/2013", "is before 1/1/2014").
    second_half = DateFilter("Calendar", "Date", date(2013, 6, 1), date(2013, 12, 31))
    wrong_table = DateFilter("Kalender", "Date", start=date(2013, 6, 1))

    async def check():
        async with fake_window(tmp_path, language) as w:
            applied = await w.check_filters(parse_page_url(WS_PAGE), [second_half])
            ignored = await w.check_filters(parse_page_url(WS_PAGE), [wrong_table])
            return applied, ignored

    applied, ignored = run(check())
    assert applied.check is FilterCheck.APPLIED
    assert ignored.check is FilterCheck.NOT_APPLIED and ignored.missing == (wrong_table,)


def test_a_date_range_from_the_page_address_is_taken_over(tmp_path):
    import json

    # Power BI narrows the date slicer to the address's range, so the slicer only mirrors the cards.
    slicers = [{"column": "Date", "kind": "range", "available": ["6/1/2013", "12/31/2013"], "selected": ["6/1/2013", "12/31/2013"]}]
    second_half = DateFilter("Calendar", "Date", date(2013, 6, 1), date(2013, 12, 31))

    async def check():
        async with fake_window(tmp_path, "en-US") as w:
            await w.open_home()
            await w.page.evaluate("s => localStorage.setItem('fake-slicers', s)", json.dumps(slicers))
            await w.page.goto(parse_page_url(WS_PAGE).with_filters([second_half]))
            await w._wait_until_rendered()
            return await w.read_set_filters()

    result = run(check())
    assert result.filters == [second_half] and result.left_out == []


@pytest.mark.parametrize("language", ["de-DE", "en-US"])
def test_a_midnight_time_on_date_cards_still_verifies(tmp_path, language):
    second_half = DateFilter("Calendar", "Date", date(2013, 6, 1), date(2013, 12, 31))

    async def check():
        async with fake_window(tmp_path, language) as w:
            await w.open_home()
            await w.page.evaluate("() => localStorage.setItem('fake-date-time', '1')")
            return await w.check_filters(parse_page_url(WS_PAGE), [second_half])

    assert run(check()).check is FilterCheck.APPLIED
