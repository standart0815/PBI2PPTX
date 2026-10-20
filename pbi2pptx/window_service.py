"""The single owner of the Power BI Window while the tool runs.

The local server never drives the window directly: it asks this service, which serialises
every operation with one lock ("Add current page" and an Export must never run at the same time).

A Hidden Export captures in an invisible browser instead. The browser profile can't be open twice,
so the Power BI Window closes for it and opens again afterwards at the page it showed.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import asdict, dataclass
from enum import Enum
from typing import AsyncIterator, Callable, Sequence

from .page_url import Filter, PageUrl
from .power_bi_window import CurrentPage, FilterVerdict, PowerBIWindow, sign_out
from .set_filters import TakeOver


class WindowNotOpen(RuntimeError):
    """The Power BI Window is starting, closed or failed; the interface tells the User what to do."""


class Busy(RuntimeError):
    """An Export is using the Power BI Window."""


class WindowState(str, Enum):
    STARTING = "starting"
    OPEN = "open"
    CLOSED = "closed"  # the User closed the window; it can be reopened
    FAILED = "failed"  # no supported browser, or it could not start
    HIDDEN_EXPORT = "hidden export"  # closed while a Hidden Export uses the profile


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


HIDDEN_RUNNING = "A hidden Export is running. The Power BI Window opens again when it has finished."


class WindowService:
    def __init__(self, factory: Callable[..., PowerBIWindow] = PowerBIWindow, language: str = "de-DE"):
        self._factory = factory  # called with the Render Language, and headless=True for a Hidden Export
        self.language = language
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
        if self._state is WindowState.HIDDEN_EXPORT:
            return WindowStatus(self._state, message=HIDDEN_RUNNING)
        if self._state is not WindowState.OPEN or window is None:
            return WindowStatus(self._state, message=self._message)
        try:
            return WindowStatus(WindowState.OPEN, window.is_signed_in(), window.browser)
        except Exception:  # noqa: BLE001 - the page went away between checks
            return WindowStatus(WindowState.CLOSED)

    async def show(self) -> None:
        """Bring the Power BI Window to the front, reopening it if the User closed it."""
        if self._state is WindowState.HIDDEN_EXPORT:
            raise Busy(HIDDEN_RUNNING)
        if self.busy and self._window is not None:  # during an Export: just show it, don't wait
            await self._window.page.bring_to_front()
            return
        async with self._lock:
            if self._state is not WindowState.OPEN:
                await self._close()
                await self._open()
            if self._window:
                await self._window.page.bring_to_front()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    async def current_page(self, include_filters: bool = False) -> tuple[CurrentPage, TakeOver | None]:
        """The page showing in the Power BI Window, for "Add current page", with the filters the User set."""
        async with self._quick_lock():
            window = self._open_window()
            current = await window.current_page()
            return current, (await window.read_set_filters() if include_filters else None)

    async def resolve(self, address: str) -> CurrentPage:
        """Open a pasted Page URL or App link in the Power BI Window and read the page it lands on."""
        async with self._quick_lock():
            window = self._open_window()
            await window.page.bring_to_front()
            return await window.resolve(address)

    async def check_filters(self, page_url: PageUrl, filters: Sequence[Filter]) -> FilterVerdict:
        """For the "Check" button: does Power BI apply these Filters on this page?"""
        async with self._quick_lock():
            window = self._open_window()
            await window.page.bring_to_front()
            return await window.check_filters(page_url, filters)

    @contextlib.asynccontextmanager
    async def exclusive(self, language: str, hidden: bool = False) -> AsyncIterator[PowerBIWindow]:
        """The window for an Export, in the Render Language, with nobody else driving it meanwhile.
        Hidden: an invisible browser on the same profile, while the Power BI Window is closed."""
        async with self._lock:
            if hidden:
                async with self._hidden_window(language) as window:
                    yield window
                return
            window = self._open_window()
            if language != self.language:
                # The browser's language is fixed at launch: reopen with the same profile (and session).
                self.language = language
                await self._close()
                await self._open()
                window = self._open_window()
            if not window.is_signed_in():
                raise WindowNotOpen("Sign in to Power BI in the Power BI Window first.")
            yield window

    @contextlib.asynccontextmanager
    async def _hidden_window(self, language: str) -> AsyncIterator[PowerBIWindow]:
        was_open = self._state is WindowState.OPEN and self._window is not None
        showing = self._window.page.url if was_open else ""
        self.language = language
        await self._close()
        self._state = WindowState.HIDDEN_EXPORT
        window = self._factory(language, headless=True)
        signed_in = False
        try:
            await window.__aenter__()
            await window.open_home()
            await window.page.wait_for_timeout(window.settle_ms)  # let a signed-out session reach the sign-in page
            signed_in = window.is_signed_in()
            if not signed_in:
                raise WindowNotOpen("The hidden Export isn't signed in to Power BI. Sign in in the Power BI Window, then export again.")
            yield window
        finally:
            with contextlib.suppress(Exception):  # it may not have started
                await window.__aexit__(None, None, None)
            self._state = WindowState.CLOSED
            if was_open or not signed_in:  # signed out: reopen so the User can sign in
                await self._open()
                if self._window and showing.startswith("https://app.powerbi.com/"):
                    with contextlib.suppress(Exception):  # the page went away: Power BI's home is fine
                        await self._window.page.goto(showing)

    @contextlib.asynccontextmanager
    async def _quick_lock(self):
        if self._lock.locked():
            raise Busy("An Export is running. Wait until it has finished.")
        async with self._lock:
            yield

    def _open_window(self) -> PowerBIWindow:
        if self._state is not WindowState.OPEN or self._window is None:
            raise WindowNotOpen("The Power BI Window isn't open. Click \"Show Power BI Window\" first.")
        return self._window

    async def sign_out(self) -> None:
        """Close the window, delete its profile (the Power BI session), and reopen it at sign-in."""
        async with self._quick_lock():
            profile = self._window.profile if self._window else None
            await self._close()
            sign_out(profile)
            await self._open()

    async def _open(self) -> None:
        self._state, self._message = WindowState.STARTING, ""
        window = self._factory(self.language)
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
