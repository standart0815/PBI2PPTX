"""The single owner of the Power BI Window while the tool runs.

The local server never drives the window directly: it asks this service, which serialises
every operation with one lock ("Add current page" and an Export must never run at the same time).
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Callable

from .power_bi_window import CurrentPage, PowerBIWindow, sign_out


class WindowNotOpen(RuntimeError):
    """The Power BI Window is starting, closed or failed; the interface tells the User what to do."""


class WindowState(str, Enum):
    STARTING = "starting"
    OPEN = "open"
    CLOSED = "closed"  # the User closed the window; it can be reopened
    FAILED = "failed"  # no supported browser, or it could not start


@dataclass
class WindowStatus:
    state: WindowState
    signed_in: bool = False
    browser: str = ""
    message: str = ""

    def to_json(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class WindowService:
    def __init__(self, factory: Callable[[], PowerBIWindow] = PowerBIWindow):
        self._factory = factory
        self._window: PowerBIWindow | None = None
        self._state = WindowState.CLOSED
        self._message = ""
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Open the Power BI Window at Power BI's home page. The User signs in there."""
        async with self._lock:
            await self._open()

    async def stop(self) -> None:
        async with self._lock:
            await self._close()

    async def status(self) -> WindowStatus:
        window = self._window
        if self._state is not WindowState.OPEN or window is None:
            return WindowStatus(self._state, message=self._message)
        try:
            return WindowStatus(WindowState.OPEN, window.is_signed_in(), window.browser)
        except Exception:  # noqa: BLE001 - the page went away between checks
            return WindowStatus(WindowState.CLOSED)

    async def show(self) -> None:
        """Bring the Power BI Window to the front, reopening it if the User closed it."""
        async with self._lock:
            if self._state is not WindowState.OPEN:
                await self._close()
                await self._open()
            if self._window:
                await self._window.page.bring_to_front()

    async def current_page(self) -> CurrentPage:
        """The page showing in the Power BI Window, for "Add current page"."""
        async with self._lock:
            return await self._open_window().current_page()

    async def resolve(self, address: str) -> CurrentPage:
        """Open a pasted Page URL or App link in the Power BI Window and read the page it lands on."""
        async with self._lock:
            window = self._open_window()
            await window.page.bring_to_front()
            return await window.resolve(address)

    def _open_window(self) -> PowerBIWindow:
        if self._state is not WindowState.OPEN or self._window is None:
            raise WindowNotOpen("The Power BI Window isn't open. Click \"Show Power BI Window\" first.")
        return self._window

    async def sign_out(self) -> None:
        """Close the window, delete its profile (the Power BI session), and reopen it at sign-in."""
        async with self._lock:
            profile = self._window.profile if self._window else None
            await self._close()
            sign_out(profile)
            await self._open()

    async def _open(self) -> None:
        self._state, self._message = WindowState.STARTING, ""
        window = self._factory()
        try:
            await window.__aenter__()
            window.context.on("close", lambda _: self._mark_closed(window))
            window.page.on("close", lambda _: self._mark_closed(window))
            await window.open_home()
        except Exception as e:  # noqa: BLE001 - reported in the interface
            self._state, self._message = WindowState.FAILED, str(e).splitlines()[0]
            self._window = None
            return
        self._window, self._state = window, WindowState.OPEN

    async def _close(self) -> None:
        window, self._window = self._window, None
        if window is not None:
            try:
                await window.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001 - already closed by the User
                pass
        if self._state is not WindowState.FAILED:
            self._state = WindowState.CLOSED

    def _mark_closed(self, window: PowerBIWindow) -> None:
        if window is self._window:
            self._state = WindowState.CLOSED
