"""The window service against the fake Power BI page, in headless Chromium."""

import asyncio

import pytest

from pbi2pptx.page_url import ReachedThrough
from pbi2pptx.power_bi_window import NotAReportPage, PowerBIWindow
from pbi2pptx.window_service import WindowNotOpen, WindowService, WindowState
from tests.test_power_bi_window import APP_LINK, WS_PAGE, _serve_fake


class FakePowerBIWindow(PowerBIWindow):
    async def __aenter__(self):
        await super().__aenter__()
        await self.context.route("https://app.powerbi.com/**", _serve_fake)
        return self


class SignedOutPowerBIWindow(FakePowerBIWindow):
    async def open_home(self):
        await self.page.goto("https://app.powerbi.com/singleSignOn")


def service_for(tmp_path, hidden_signed_in=True):
    profile = tmp_path / "profile"
    opened = []  # "visible" / "hidden", in order

    def factory(language, headless=False):
        opened.append("hidden" if headless else "visible")
        kind = SignedOutPowerBIWindow if headless and not hidden_signed_in else FakePowerBIWindow
        return kind(language=language, profile=profile, browsers=(None,), headless=True, settle_ms=100, overlay_wait_ms=600)

    service = WindowService(factory)
    service.opened = opened
    return service, profile


def test_opens_the_window_signed_in(tmp_path):
    async def check():
        service, _ = service_for(tmp_path)
        await service.start()
        status = await service.status()
        await service.stop()
        return status, await service.status()

    open_status, stopped = asyncio.run(check())
    assert (open_status.state, open_status.signed_in, open_status.browser) == (WindowState.OPEN, True, "chromium")
    assert stopped.state is WindowState.CLOSED


def test_notices_a_closed_window_and_reopens_it(tmp_path):
    async def check():
        service, _ = service_for(tmp_path)
        await service.start()
        await service._window.page.close()
        await asyncio.sleep(0.2)
        closed = (await service.status()).state
        await service.show()
        reopened = (await service.status()).state
        await service.stop()
        return closed, reopened

    assert asyncio.run(check()) == (WindowState.CLOSED, WindowState.OPEN)


def test_sign_out_deletes_the_profile_and_reopens(tmp_path):
    async def check():
        service, profile = service_for(tmp_path)
        await service.start()
        marker = profile / "marker"
        marker.write_text("session")
        await service.sign_out()
        status = await service.status()
        await service.stop()
        return marker.exists(), status.state

    assert asyncio.run(check()) == (False, WindowState.OPEN)


def test_reports_a_missing_browser(tmp_path):
    async def check():
        service = WindowService(lambda language: PowerBIWindow(language, profile=tmp_path / "p", browsers=("no-such-browser",), headless=True))
        await service.start()
        return await service.status()

    status = asyncio.run(check())
    assert status.state is WindowState.FAILED
    assert "No supported browser" in status.message


def test_add_current_page_and_paste_an_app_link(tmp_path):
    async def check():
        service, _ = service_for(tmp_path)
        await service.start()
        try:
            with pytest.raises(NotAReportPage):  # the window starts at Power BI's home page
                await service.current_page()
            await service._window.page.goto(WS_PAGE)
            current, taken = await service.current_page(include_filters=True)
            assert taken.filters == [] and taken.left_out == []
            pasted = await service.resolve(APP_LINK)
        finally:
            await service.stop()
        return current, pasted

    current, pasted = asyncio.run(check())
    assert (current.page_name, current.page_url.reached_through) == ("Umsatz", ReachedThrough.WORKSPACE)
    assert (pasted.page_name, pasted.page_url.reached_through) == ("Umsatz", ReachedThrough.POWER_BI_APP)


def test_adding_needs_an_open_window(tmp_path):
    async def check():
        service, _ = service_for(tmp_path)
        await service.current_page()

    with pytest.raises(WindowNotOpen):
        asyncio.run(check())


# --- Hidden Export ----------------------------------------------------------------------------

from pbi2pptx.window_service import Busy  # noqa: E402


def test_hidden_export_closes_the_window_and_reopens_it_where_it_was(tmp_path):
    async def check():
        service, _ = service_for(tmp_path)
        await service.start()
        await service._window.page.goto(WS_PAGE)
        async with service.exclusive("en-US", hidden=True) as window:
            during = await service.status()
            try:
                await service.show()
                shown = "shown"
            except Busy as e:
                shown = str(e)
            used = (window.headless, window.language, window.is_signed_in())
        after = await service.status()
        url = service._window.page.url
        await service.stop()
        return service.opened, during, shown, used, after.state, url

    opened, during, shown, used, after, url = asyncio.run(check())
    assert opened == ["visible", "hidden", "visible"]
    assert during.state is WindowState.HIDDEN_EXPORT and "hidden Export is running" in during.message
    assert "hidden Export is running" in shown
    assert used == (True, "en-US", True)
    assert (after, url) == (WindowState.OPEN, WS_PAGE)


def test_a_signed_out_hidden_export_stops_and_reopens_the_window_to_sign_in(tmp_path):
    async def check():
        service, _ = service_for(tmp_path, hidden_signed_in=False)
        await service.start()
        try:
            async with service.exclusive("de-DE", hidden=True):
                return "ran"
        except WindowNotOpen as e:
            refused = str(e)
        state = (await service.status()).state
        await service.stop()
        return refused, state

    refused, state = asyncio.run(check())
    assert "isn't signed in" in refused
    assert state is WindowState.OPEN

