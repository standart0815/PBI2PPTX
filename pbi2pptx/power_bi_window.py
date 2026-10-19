"""The Power BI Window: an installed browser with its own persistent profile, driven by Playwright.

The User signs in and browses here. The tool reads the current page from it and captures
Page Images in it. Everything that depends on the Power BI interface comes from power_bi_ui.
"""

from __future__ import annotations

import asyncio
import os
import platform
import re
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Sequence

from playwright.async_api import BrowserContext, Page, async_playwright

from . import power_bi_ui as ui
from .page_url import Filter, PageUrl, is_app_link, parse_page_url
from .set_filters import FilterCard, Slicer, TakeOver, take_over


def profile_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / "PBI2PPTX" / "profile"


def installed_browsers() -> tuple:
    """Playwright channels of installed browsers, in order of preference."""
    return ("msedge", "chrome") if platform.system() == "Windows" else ("chrome", "msedge")


def sign_out(profile: Path | None = None) -> None:
    """Delete the Power BI Window's profile, and with it the Power BI session."""
    shutil.rmtree(profile or profile_dir(), ignore_errors=True)


async def _wait_for_profile_release(profile: Path, timeout_s: float = 30) -> None:
    # Chrome holds the profile until its last process exits, a few seconds after closing.
    lock = profile / "SingletonLock"
    deadline = time.monotonic() + timeout_s
    while (lock.exists() or lock.is_symlink()) and time.monotonic() < deadline:
        await asyncio.sleep(0.5)


class SignIn(str, Enum):
    SIGNED_IN = "signed in"
    TIMEOUT = "timeout"
    WINDOW_CLOSED = "window closed"


@dataclass(frozen=True)
class CurrentPage:
    page_url: PageUrl
    page_name: str
    report_name: str


class FilterCheck(str, Enum):
    NO_FILTERS = "no filters"
    APPLIED = "applied"
    NOT_APPLIED = "not applied"
    NOT_VERIFIABLE = "not verifiable"  # the report hides its filter pane


@dataclass(frozen=True)
class FilterVerdict:
    check: FilterCheck
    missing: tuple = ()  # the Filters Power BI didn't apply


@dataclass
class CaptureReport:
    """What happened while capturing one page, for the Export log and the self-check."""

    reset: str = "not tried"
    fit_to_page: str = "not tried"
    filters: FilterCheck = FilterCheck.NO_FILTERS
    seconds: float = 0.0
    notes: list = field(default_factory=list)


class NotAReportPage(RuntimeError):
    """The address shows no report page: deleted, no access, or not a page at all."""


class FiltersNotApplied(RuntimeError):
    """Power BI ignored at least one Filter (wrong table or column name); capturing would mislead."""

    def __init__(self, missing: tuple):
        super().__init__("Power BI did not apply: " + "; ".join(str(f) for f in missing))
        self.missing = missing


def card_shows(title: str, f: Filter) -> bool:
    """Whether a filter card title such as "Country ist Germany oder France" shows exactly the Filter's values."""
    if not title.startswith(f.column + " "):
        return False
    _operator, _, shown = title[len(f.column) + 1 :].partition(" ")  # "ist" / "is"
    values = {v.strip() for v in re.split(ui.FILTER_CARD_VALUE_SEPARATORS, shown)}
    return set(f.values) <= values


class PowerBIWindow:
    """Use as `async with PowerBIWindow() as window:`. Only one task may drive it at a time."""

    def __init__(
        self,
        language: str = "de-DE",
        profile: Path | None = None,
        browsers: Sequence[str | None] | None = None,
        headless: bool = False,
        viewport: tuple = (1600, 1000),
        settle_ms: int = 2000,
        overlay_wait_ms: int = 1500,
    ):
        self.language = language
        self.profile = profile or profile_dir()
        self.browsers = tuple(browsers) if browsers is not None else installed_browsers()  # None = bundled Chromium
        self.headless = headless
        self.viewport = viewport
        self.settle_ms = settle_ms
        self.overlay_wait_ms = overlay_wait_ms
        self.browser = ""
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._pw = None

    async def __aenter__(self) -> "PowerBIWindow":
        await _wait_for_profile_release(self.profile)
        self._pw = await async_playwright().start()
        errors = []
        for channel in self.browsers:
            options = dict(
                headless=self.headless,
                locale=self.language,
                args=[f"--lang={self.language}"],
                viewport={"width": self.viewport[0], "height": self.viewport[1]},
                device_scale_factor=2,
                timeout=60_000,
            )
            if channel:
                options["channel"] = channel
            try:
                self.context = await self._pw.chromium.launch_persistent_context(str(self.profile), **options)
                self.browser = channel or "chromium"
                break
            except Exception as e:  # noqa: BLE001 - try the next installed browser
                errors.append(f"{channel or 'chromium'}: {str(e).splitlines()[0]}")
        if self.context is None:
            await self._pw.stop()
            raise RuntimeError("No supported browser found. " + " | ".join(errors))
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        return self

    async def __aexit__(self, *exc) -> None:
        try:
            await self.context.close()
        except Exception:  # noqa: BLE001 - the User may already have closed the window
            pass
        await self._pw.stop()
        await _wait_for_profile_release(self.profile)

    # --- Sign-in -----------------------------------------------------------------------------

    async def open_home(self) -> None:
        await self.page.goto(ui.HOME)

    def is_signed_in(self) -> bool:
        url = self.page.url
        return url.startswith("https://app.powerbi.com/") and not any(m in url for m in ui.SIGNED_OUT_MARKERS)

    async def wait_for_sign_in(self, timeout_s: float = 600) -> SignIn:
        """Wait while the User signs in in the window. The tool never sees the credentials."""
        if not self.page.url.startswith("https://app.powerbi.com/"):
            await self.open_home()
        deadline = time.monotonic() + timeout_s
        try:
            while time.monotonic() < deadline:
                await self.page.wait_for_timeout(1000)
                if self.is_signed_in():
                    await self.page.wait_for_timeout(2000)  # let Power BI finish its redirects
                    if self.is_signed_in():
                        return SignIn.SIGNED_IN
        except Exception as e:  # noqa: BLE001
            if "closed" in str(e):
                return SignIn.WINDOW_CLOSED
            raise
        return SignIn.TIMEOUT

    # --- Reading the current page ------------------------------------------------------------

    async def current_page(self) -> CurrentPage:
        """The page showing now, for "Add current page". Raises NotAReportPage elsewhere."""
        try:
            page_url = parse_page_url(self.page.url)
        except ValueError:
            raise NotAReportPage("The Power BI Window is not showing a report page") from None
        name = await self._first_text(ui.CURRENT_PAGE_NAME) or page_url.page
        return CurrentPage(page_url, name, await self._report_name(name))

    async def resolve(self, url: str) -> CurrentPage:
        """Open a pasted address (Page URL or shared App link) and return the page it lands on."""
        if not is_app_link(url):
            parse_page_url(url)  # fail fast on anything that is not a Page URL
        await self._open(url)
        return await self.current_page()

    async def _first_text(self, selectors: Sequence[str]) -> str:
        for selector in selectors:
            loc = self.page.locator(selector).first
            try:
                if await loc.count() and await loc.is_visible():
                    text = (await loc.inner_text(timeout=1000)).strip()
                    if text:
                        return text.splitlines()[0].strip()
            except Exception:  # noqa: BLE001 - try the next selector
                continue
        return ""

    async def _report_name(self, page_name: str) -> str:
        button = self.page.locator(ui.REPORT_NAME).first
        try:
            if await button.count():
                label = (await button.get_attribute("aria-label") or "").strip()
                if label:
                    return label
        except Exception:  # noqa: BLE001 - fall back to the title
            pass
        title = (await self.page.title()).rsplit(ui.TITLE_SUFFIX_SEPARATOR, 1)[0].strip()
        prefix = page_name + ui.TITLE_PAGE_SEPARATOR
        return title[len(prefix):] if title.startswith(prefix) else title

    # --- Capturing ---------------------------------------------------------------------------

    async def capture(self, page_url: PageUrl, filters: Sequence[Filter], out: Path) -> CaptureReport:
        """Capture one Report Page in its Default State with its Filters applied, as a PNG."""
        started = time.monotonic()
        report = CaptureReport()

        # 1. The page with its Filters. URL filters don't enable "Reset to default" (seen 2026-10-19),
        #    so an enabled reset button means saved personal changes: reset them, then reopen the
        #    page in case the reset also dropped the Filters.
        target = page_url.with_filters(filters)
        await self._open(target)
        await self._dismiss_overlays()
        if await self._click(ui.RESET_BUTTON_TEXTS):
            report.reset = "confirmed" if await self._confirm_reset() else "clicked, but no confirmation found"
            await self._wait_until_rendered()
            if filters:
                await self._open(target)
        else:
            report.reset = "not needed"

        # 2. Did Power BI apply the Filters? A Filter it ignored would give a misleading slide.
        if filters:
            verdict = await self.verify_filters(filters)
            report.filters = verdict.check
            if verdict.check is FilterCheck.NOT_APPLIED:
                raise FiltersNotApplied(verdict.missing)

        # 3. Fit to page.
        if await self._is_fit_to_page():
            report.fit_to_page = "already set"
        elif await self._click(ui.VIEW_TAB_TEXTS, role="tab") and (
            await self._click(ui.FIT_TO_PAGE_TEXTS) or await self._click(ui.FIT_TO_PAGE_TEXTS, role="menuitem")
        ):
            await self._wait_until_rendered()
            report.fit_to_page = "set" if await self._is_fit_to_page() else "clicked, but not in fit-to-page"
        else:
            await self.page.keyboard.press("Escape")
            report.fit_to_page = "control not found"

        # 4. Clear tips (they appear a few seconds after load) and hover toolbars, then capture.
        for _ in range(3):
            await self._dismiss_overlays()
            await self.page.mouse.move(1, 1)
            await self.page.wait_for_timeout(self.overlay_wait_ms)
            if not await self._visible_overlays():
                break
        left = await self._visible_overlays()
        if left:
            report.notes.append("overlay still visible: " + ", ".join(left))
        await self.page.add_style_tag(content=ui.CAPTURE_CSS)
        await self.page.evaluate("() => document.activeElement && document.activeElement.blur()")
        await self.page.wait_for_timeout(300)
        box = await self.page.locator(ui.CANVAS).first.bounding_box()
        out.parent.mkdir(parents=True, exist_ok=True)
        # A clip of the page, not an element screenshot: Power BI keeps re-laying out the canvas,
        # and element screenshots wait for it to be "stable".
        await self.page.screenshot(path=str(out), clip=box)
        report.seconds = round(time.monotonic() - started, 1)
        return report

    async def check_filters(self, page_url: PageUrl, filters: Sequence[Filter]) -> FilterVerdict:
        """For the "Check" button: open the page with its Filters and verify them, without capturing."""
        await self._open(page_url.with_filters(filters))
        await self._dismiss_overlays()
        return await self.verify_filters(filters)

    async def verify_filters(self, filters: Sequence[Filter]) -> FilterVerdict:
        """Read Power BI's filter pane: every Filter it applied shows as a card with its values."""
        if not filters:
            return FilterVerdict(FilterCheck.NO_FILTERS)
        opened = False
        pane = self.page.locator(ui.FILTER_PANE)
        if not await pane.count():
            if not await self._click(ui.FILTER_PANE_TOGGLE_TEXTS):
                return FilterVerdict(FilterCheck.NOT_VERIFIABLE)
            opened = True
            try:
                await self.page.locator(ui.FILTER_CARD_TITLES).first.wait_for(state="visible", timeout=10_000)
            except Exception:  # noqa: BLE001 - pane without cards: nothing applied
                pass
        titles = [" ".join(t.split()) for t in await self.page.locator(ui.FILTER_CARD_TITLES).all_inner_texts()]
        missing = tuple(f for f in filters if not any(card_shows(t, f) for t in titles))
        if opened:
            await self._click(ui.FILTER_PANE_TOGGLE_TEXTS)  # close it again: the open pane narrows the canvas
            try:
                await pane.wait_for(state="detached", timeout=10_000)
            except Exception:  # noqa: BLE001
                pass
            await self.page.wait_for_timeout(self.settle_ms)
        return FilterVerdict(FilterCheck.NOT_APPLIED if missing else FilterCheck.APPLIED, missing)

    async def read_set_filters(self) -> TakeOver:
        """For "Add current page": the filters the Filter Pane and the slicers show right now."""
        cards = []
        opened = False
        if not await self.page.locator(ui.FILTER_PANE).count():
            opened = await self._click(ui.FILTER_PANE_TOGGLE_TEXTS)
            if opened:
                try:
                    await self.page.locator(ui.FILTER_CARD_TITLES).first.wait_for(state="visible", timeout=10_000)
                except Exception:  # noqa: BLE001 - a pane without cards
                    pass
        if await self.page.locator(ui.FILTER_PANE).count():
            raw = await self.page.evaluate(
                """([cards, field, restatement]) => [...document.querySelectorAll(cards)].map(card => ({
                    field: card.querySelector(field)?.getAttribute('title') || '',
                    condition: card.querySelector(restatement)?.getAttribute('title') || '',
                }))""",
                [ui.FILTER_CARD_TITLES, ui.FILTER_CARD_FIELD, ui.FILTER_CARD_RESTATEMENT],
            )
            for index, item in enumerate(raw):
                ticked = ()
                if re.search(ui.ABBREVIATED, item["condition"]):
                    ticked = await self._ticked_values_of_card(index)
                cards.append(FilterCard(item["field"], item["condition"], ticked))
        if opened:
            await self._click(ui.FILTER_PANE_TOGGLE_TEXTS)  # close it again: the open pane narrows the canvas
            await self.page.wait_for_timeout(self.settle_ms)

        raw_slicers = await self.page.evaluate(
            """([slicer, header, item, dropdown, range, selectAll]) => [...document.querySelectorAll('.visualContainer')]
                .filter(v => v.matches(slicer))
                .map(v => {
                    const items = [...v.querySelectorAll(item)];
                    const all = items.find(i => selectAll.includes((i.getAttribute('title') || '').trim()));
                    const values = items.filter(i => i !== all && i.getAttribute('aria-checked') === 'true')
                        .map(i => (i.getAttribute('title') || i.innerText).trim());
                    let scrollable = false;
                    for (let e = items[0]?.parentElement; e && e !== v; e = e.parentElement)
                        if (e.scrollHeight > e.clientHeight + 2) { scrollable = true; break; }
                    const drop = v.querySelector(dropdown);
                    return {
                        column: (v.querySelector(header)?.innerText || '').trim(),
                        kind: v.querySelector(range) ? 'range' : drop ? 'dropdown' : 'list',
                        ticked: values,
                        selectAll: all ? all.getAttribute('aria-checked') || '' : '',
                        dropdownText: drop ? drop.innerText.trim() : '',
                        scrollable,
                    };
                })""",
            [ui.SLICER, ui.SLICER_HEADER, ui.SLICER_ITEM, ui.SLICER_DROPDOWN, ui.SLICER_RANGE, list(ui.SELECT_ALL)],
        )
        slicers = [
            Slicer(s["column"], s["kind"], tuple(s["ticked"]), s["selectAll"], s["dropdownText"], s["scrollable"])
            for s in raw_slicers
            if s["column"]
        ]
        return take_over(cards, slicers)

    async def _ticked_values_of_card(self, index: int) -> tuple:
        """Open a card whose condition Power BI shortened and read every ticked value (best effort)."""
        card = self.page.locator(ui.FILTER_CARD_TITLES).nth(index)
        try:
            await card.click()
            await self.page.wait_for_timeout(1000)
            container = card.locator("xpath=..")
            values = await container.locator(ui.FILTER_CARD_CHECKED).evaluate_all(
                "(els, selectAll) => els.map(e => (e.getAttribute('title') || e.innerText || '').trim())"
                ".filter(v => v && !selectAll.includes(v))",
                list(ui.SELECT_ALL),
            )
            await card.click()  # fold it again
            return tuple(values)
        except Exception:  # noqa: BLE001 - not readable: the Filter is left out, never taken over incomplete
            return ()

    async def _open(self, url: str) -> None:
        await self.page.goto(url)
        await self._wait_until_rendered()
        if "/reports/" not in self.page.url or not await self.page.locator(ui.CANVAS).count():
            raise NotAReportPage(
                f"No report page at this address (deleted or no access?) – Power BI showed {self.page.url.split('?')[0]}"
            )

    async def _wait_until_rendered(self, timeout_ms: int = 60_000) -> None:
        # Either the canvas appears, or Power BI leaves the report (deleted page, no access).
        try:
            await self.page.wait_for_function(
                f"() => document.querySelector('{ui.CANVAS}') || !location.pathname.includes('/reports/')",
                timeout=timeout_ms,
            )
        except Exception:  # noqa: BLE001 - _open() reports a missing canvas
            return
        try:
            # Power BI keeps background connections open, so "network idle" may never come.
            await self.page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:  # noqa: BLE001
            pass
        for selector in ui.SPINNERS:
            try:
                await self.page.locator(selector).first.wait_for(state="hidden", timeout=10_000)
            except Exception:  # noqa: BLE001 - selector may not exist in this Power BI version
                pass
        await self.page.wait_for_timeout(self.settle_ms)  # visuals animate in after loading

    async def _is_fit_to_page(self) -> bool:
        canvas = self.page.locator(ui.CANVAS).first
        return bool(await canvas.count()) and ui.FIT_TO_PAGE_CLASS in (await canvas.get_attribute("class") or "")

    async def _click(self, texts: Sequence[str], role: str = "button") -> bool:
        for text in texts:
            loc = self.page.get_by_role(role, name=text, exact=False).first
            try:
                if await loc.count() and await loc.is_visible() and await loc.is_enabled():
                    await loc.click(timeout=3000)
                    return True
            except Exception:  # noqa: BLE001 - try the next text
                continue
        return False

    async def _confirm_reset(self) -> bool:
        dialog = self.page.locator(ui.DIALOGS).last
        try:
            await dialog.wait_for(state="visible", timeout=5000)
        except Exception:  # noqa: BLE001 - some versions reset without asking
            return False
        for text in ui.RESET_CONFIRM_TEXTS:
            button = dialog.get_by_role("button", name=text, exact=True)
            if await button.count():
                await button.first.click()
                await dialog.wait_for(state="hidden", timeout=10_000)
                return True
        return False

    async def _dismiss_overlays(self) -> None:
        for _ in range(3):  # one tip can lead to the next
            dismissed = False
            tutorial = self.page.locator(f"{ui.TUTORIAL_DISMISS}:visible").first
            if await tutorial.count():
                await tutorial.click()
                await self.page.wait_for_timeout(300)
                dismissed = True
            for selector in ui.OVERLAYS:
                overlay = self.page.locator(f"{selector}:visible").first
                if not await overlay.count():
                    continue
                for text in ui.DISMISS_TEXTS:
                    button = overlay.get_by_role("button", name=text, exact=True)
                    if await button.count() and await button.first.is_visible():
                        await button.first.click()
                        await self.page.wait_for_timeout(300)
                        dismissed = True
                        break
            if not dismissed:
                return

    async def _visible_overlays(self) -> list:
        return [s for s in ui.OVERLAYS if await self.page.locator(f"{s}:visible").count()]
