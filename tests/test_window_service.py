"""The window service against the fake Power BI page, in headless Chromium."""

import asyncio

from pbi2pptx.power_bi_window import PowerBIWindow
from pbi2pptx.window_service import WindowService, WindowState
from tests.test_power_bi_window import _serve_fake


class FakePowerBIWindow(PowerBIWindow):
    async def __aenter__(self):
        await super().__aenter__()
        await self.context.route("https://app.powerbi.com/**", _serve_fake)
        return self


def service_for(tmp_path):
    profile = tmp_path / "profile"
    return WindowService(lambda: FakePowerBIWindow(profile=profile, browsers=(None,), headless=True, settle_ms=100)), profile


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
        service = WindowService(lambda: PowerBIWindow(profile=tmp_path / "p", browsers=("no-such-browser",), headless=True))
        await service.start()
        return await service.status()

    status = asyncio.run(check())
    assert status.state is WindowState.FAILED
    assert "No supported browser" in status.message
