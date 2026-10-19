"""The Power BI Window: an installed browser with its own persistent profile, driven by Playwright.

Everything here depends on the Power BI web interface, which Microsoft can change without
notice (ADR 0003). Selectors and button texts are collected in one place so they are easy to
adjust after a Power BI release.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from playwright.sync_api import BrowserContext, Page, sync_playwright

POWER_BI = "https://app.powerbi.com/"

# Candidate selectors for the report canvas, most specific first.
CANVAS_SELECTORS = ["div.displayArea", "[class*='displayArea']", "exploration-container .canvasFlexBox", "exploration-container"]
# Button texts per interface language.
RESET_TEXTS = ["Reset to default", "Auf Standard zurücksetzen", "Auf Standardwert zurücksetzen"]
RESET_CONFIRM_TEXTS = ["Zurücksetzen", "Reset"]  # exact, inside the confirmation dialog
# Tips and promotions Power BI lays over the canvas (teaching bubbles, "what's new" dialogs).
DISMISS_TEXTS = ["Vielleicht später", "Maybe later", "Nicht jetzt", "Not now", "Verstanden", "Got it", "Schließen", "Close"]
OVERLAY_SELECTORS = [".tutorial-popup", ".ms-TeachingBubble", "[role=dialog]", "[role=alertdialog]"]
TUTORIAL_DISMISS = ".tutorial-popup button.cancel"  # "Vielleicht später" / "Maybe later", any language
# Icon toolbars that visuals show on hover or focus (not the visual titles).
CAPTURE_CSS = ".optionsMenu, visual-container-options-menu { visibility: hidden !important; }"
VIEW_TAB_TEXTS = ["View", "Anzeigen"]  # ribbon tab, role=tab
FIT_TO_PAGE_TEXTS = ["Fit to page", "An Seite anpassen", "Seite anpassen"]
SPINNER_SELECTORS = [".circle-spinner", ".powerbi-spinner", "[class*='spinner']:visible"]

PAGE_URL = re.compile(
    r"^https://app\.powerbi\.com/groups/(?P<workspace>[^/]+)/(?:apps/(?P<app>[^/]+)/)?reports/(?P<report>[0-9a-f-]{36})/(?P<page>[^/?#]+)",
    re.IGNORECASE,
)


def profile_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / "PBI2PPTX" / "profile"


def _wait_for_profile_release(timeout_s: float = 30) -> None:
    """Chrome holds the profile until its last process exits, a few seconds after closing."""
    lock = profile_dir() / "SingletonLock"
    deadline = time.time() + timeout_s
    while (lock.exists() or lock.is_symlink()) and time.time() < deadline:
        time.sleep(0.5)


def browser_channels() -> List[str]:
    """Installed browsers to try, in order of preference."""
    return ["msedge", "chrome"] if platform.system() == "Windows" else ["chrome", "msedge"]


# --- Page URLs and Filters -------------------------------------------------------------------


@dataclass(frozen=True)
class PageRef:
    workspace: str  # "me" for My workspace and for Power BI Apps
    app: Optional[str]
    report: str
    page: str
    ctid: Optional[str] = None

    @property
    def via(self) -> str:
        if self.app:
            return "Power BI App"
        return "My workspace" if self.workspace == "me" else "Workspace"

    @property
    def url(self) -> str:
        path = f"groups/{self.workspace}/" + (f"apps/{self.app}/" if self.app else "") + f"reports/{self.report}/{self.page}"
        return POWER_BI + path + (f"?ctid={self.ctid}" if self.ctid else "")


def parse_page_url(url: str) -> PageRef:
    match = PAGE_URL.match(url.strip())
    if not match:
        raise ValueError(f"Not a Power BI report page URL: {url}")
    query = dict(parse_qsl(urlsplit(url).query))
    return PageRef(match["workspace"], match["app"], match["report"], match["page"], query.get("ctid"))


@dataclass(frozen=True)
class Filter:
    table: str
    column: str
    values: tuple

    @classmethod
    def parse(cls, text: str) -> "Filter":
        target, _, values = text.partition("=")
        table, _, column = target.partition("/")
        if not (table.strip() and column.strip() and values.strip()):
            raise ValueError(f"Filter must look like 'Table/Column=Value1,Value2', got: {text}")
        return cls(table.strip(), column.strip(), tuple(v.strip() for v in values.split(",")))

    def __str__(self) -> str:
        return f"{self.table}/{self.column} = {', '.join(self.values)}"


def _escape_name(name: str) -> str:
    # Power BI URL filters encode special characters in table/column names as _xHHHH_.
    return "".join(c if c.isalnum() or c == "_" else f"_x{ord(c):04X}_" for c in name)


def _literal(value: str) -> str:
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return value
    return "'" + value.replace("'", "''") + "'"


def filter_expression(filters: List[Filter]) -> str:
    parts = []
    for f in filters:
        target = f"{_escape_name(f.table)}/{_escape_name(f.column)}"
        if len(f.values) == 1:
            parts.append(f"{target} eq {_literal(f.values[0])}")
        else:
            parts.append(f"{target} in ({','.join(_literal(v) for v in f.values)})")
    return " and ".join(parts)


def page_url_with_filters(ref: PageRef, filters: List[Filter]) -> str:
    if not filters:
        return ref.url
    scheme, netloc, path, query, frag = urlsplit(ref.url)
    params = dict(parse_qsl(query))
    params["filter"] = filter_expression(filters)
    return urlunsplit((scheme, netloc, path, urlencode(params, quote_via=quote), frag))


# --- The window ------------------------------------------------------------------------------


@dataclass
class CaptureReport:
    """What happened while capturing one page; the spike prints it so the checks are visible."""

    reset: str = "not tried"
    fit_to_page: str = "not tried"
    canvas_selector: str = ""
    notes: List[str] = field(default_factory=list)


class PowerBIWindow:
    def __init__(self, language: str = "de-DE", width: int = 1600, height: int = 1000):
        self.language, self.width, self.height = language, width, height
        self._pw = None
        self.context: Optional[BrowserContext] = None
        self.channel = ""

    def __enter__(self) -> "PowerBIWindow":
        _wait_for_profile_release()
        self._pw = sync_playwright().start()
        errors = []
        for channel in browser_channels():
            try:
                self.context = self._pw.chromium.launch_persistent_context(
                    str(profile_dir()),
                    channel=channel,
                    headless=False,
                    locale=self.language,
                    args=[f"--lang={self.language}"],
                    viewport={"width": self.width, "height": self.height},
                    device_scale_factor=2,
                    timeout=60_000,
                )
                self.channel = channel
                break
            except Exception as e:  # noqa: BLE001 - try the next installed browser
                errors.append(f"{channel}: {str(e).splitlines()[0]}")
        if self.context is None:
            self._pw.stop()
            raise RuntimeError("No supported browser found. " + " | ".join(errors))
        return self

    def __exit__(self, *exc) -> None:
        try:
            self.context.close()
        except Exception:  # noqa: BLE001 - the User may already have closed the window
            pass
        self._pw.stop()
        _wait_for_profile_release()

    @property
    def page(self) -> Page:
        return self.context.pages[0] if self.context.pages else self.context.new_page()

    def open_power_bi(self) -> None:
        if not self.page.url.startswith(POWER_BI):
            self.page.goto(POWER_BI)

    def current_page(self) -> tuple:
        """The Page URL showing now, plus the best guess at the page's display name."""
        ref = parse_page_url(self.page.url)
        return ref, self._page_display_name() or ref.page

    def _page_display_name(self) -> str:
        candidates = [
            # Workspace reports: the pages pane, not the ribbon (whose tabs are also role=tab).
            "exploration-fluent-navigation [role='tab'][aria-selected='true']",
            "section.newLookPageNav [role='tab'][aria-selected='true']",
            # Power BI Apps: the App's navigation, where the current page is a link.
            "mat-list div.itemRow[role='link'][aria-current='page']",
        ]
        for selector in candidates:
            loc = self.page.locator(selector).first
            try:
                if loc.count() and loc.is_visible():
                    text = loc.inner_text(timeout=1000).strip()
                    if text:
                        return text.splitlines()[0]
            except Exception:  # noqa: BLE001
                continue
        return ""

    def _click_text(self, texts: List[str], role: str = "button") -> bool:
        for text in texts:
            loc = self.page.get_by_role(role, name=text, exact=False).first
            try:
                if loc.count() and loc.is_visible() and loc.is_enabled():
                    loc.click(timeout=3000)
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def _wait_until_rendered(self, timeout_ms: int = 60_000) -> None:
        try:
            # Power BI keeps background connections open, so "network idle" may never come.
            self.page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.page.locator("div.displayArea").first.wait_for(state="visible", timeout=timeout_ms)
        except Exception:  # noqa: BLE001 - no canvas: redirected, no access; capture() reports it
            return
        for selector in SPINNER_SELECTORS:
            try:
                self.page.locator(selector).first.wait_for(state="hidden", timeout=timeout_ms)
            except Exception:  # noqa: BLE001 - selector may not exist in this Power BI version
                pass
        self.page.wait_for_timeout(2000)  # visuals animate in after the network settles

    def _is_fit_to_page(self) -> bool:
        loc = self.page.locator("div.displayArea").first
        return bool(loc.count()) and "fitToPage" in (loc.get_attribute("class") or "")

    def _canvas(self, report: CaptureReport):
        for selector in CANVAS_SELECTORS:
            loc = self.page.locator(selector).first
            try:
                if loc.count() and loc.is_visible():
                    report.canvas_selector = selector
                    return loc
            except Exception:  # noqa: BLE001
                continue
        raise RuntimeError("Report canvas not found; see 'probe' and adjust CANVAS_SELECTORS")

    def capture(self, ref: PageRef, filters: List[Filter], out: Path) -> CaptureReport:
        report = CaptureReport()
        # 1. Reset on the plain page, so a reset can never remove the Entry's Filters.
        self._open(ref.url)
        self._dismiss_overlays()
        if self._click_text(RESET_TEXTS):
            report.reset = "confirmed" if self._confirm_reset() else "clicked, but confirmation not found"
            self._wait_until_rendered()
        else:
            report.reset = "button not found or disabled (nothing to reset?)"

        # 2. Then the page with its Filters.
        if filters:
            self._open(page_url_with_filters(ref, filters))

        if self._is_fit_to_page():
            report.fit_to_page = "already set"
        elif self._click_text(VIEW_TAB_TEXTS, role="tab") and (
            self._click_text(FIT_TO_PAGE_TEXTS) or self._click_text(FIT_TO_PAGE_TEXTS, role="menuitem")
        ):
            self._wait_until_rendered()
            report.fit_to_page = "set" if self._is_fit_to_page() else "clicked, but canvas not in fit-to-page"
        else:
            self.page.keyboard.press("Escape")
            report.fit_to_page = "control not found"

        # 3. Clear tips (they appear a few seconds after load) and hover toolbars, then capture.
        for _ in range(3):
            self._dismiss_overlays()
            self.page.mouse.move(1, 1)
            self.page.wait_for_timeout(1500)
            if not self._visible_overlays():
                break
        left = self._visible_overlays()
        if left:
            report.notes.append("overlay still visible: " + ", ".join(left))
        self.page.add_style_tag(content=CAPTURE_CSS)
        self.page.evaluate("() => document.activeElement && document.activeElement.blur()")
        self.page.wait_for_timeout(300)
        box = self._canvas(report).bounding_box()
        out.parent.mkdir(parents=True, exist_ok=True)
        # A clip of the page, not an element screenshot: Power BI keeps re-laying out the canvas,
        # and element screenshots wait for it to be "stable".
        self.page.screenshot(path=str(out), clip=box)
        return report

    def _open(self, url: str) -> None:
        self.page.goto(url)
        self._wait_until_rendered()
        if "/reports/" not in self.page.url or not self.page.locator("div.displayArea").count():
            raise RuntimeError(f"No report page at this address (deleted or no access?) – Power BI showed {self.page.url.split('?')[0]}")

    def _confirm_reset(self) -> bool:
        dialog = self.page.locator("[role=dialog], [role=alertdialog]").last
        try:
            dialog.wait_for(state="visible", timeout=5000)
        except Exception:  # noqa: BLE001 - some versions reset without asking
            return False
        for text in RESET_CONFIRM_TEXTS:
            button = dialog.get_by_role("button", name=text, exact=True)
            if button.count():
                button.first.click()
                dialog.wait_for(state="hidden", timeout=10_000)
                return True
        return False

    def _dismiss_overlays(self) -> None:
        for _ in range(3):  # one tip can lead to the next
            dismissed = False
            tutorial = self.page.locator(f"{TUTORIAL_DISMISS}:visible").first
            if tutorial.count():
                tutorial.click()
                self.page.wait_for_timeout(500)
                dismissed = True
            for selector in OVERLAY_SELECTORS:
                overlay = self.page.locator(f"{selector}:visible").first
                if not overlay.count():
                    continue
                for text in DISMISS_TEXTS:
                    button = overlay.get_by_role("button", name=text, exact=True)
                    if button.count() and button.first.is_visible():
                        button.first.click()
                        self.page.wait_for_timeout(500)
                        dismissed = True
                        break
            if not dismissed:
                return

    def _visible_overlays(self) -> List[str]:
        return [s for s in OVERLAY_SELECTORS if self.page.locator(f"{s}:visible").count()]

    def probe(self) -> List[str]:
        """Large visible elements and buttons, to find canvas selectors and button texts."""
        return self.page.evaluate(
            """() => {
              const out = [];
              for (const el of document.querySelectorAll('div, exploration-container, section')) {
                const r = el.getBoundingClientRect();
                if (r.width > 600 && r.height > 300 && el.className && typeof el.className === 'string')
                  out.push(`${Math.round(r.width)}x${Math.round(r.height)} @${Math.round(r.x)},${Math.round(r.y)}  <${el.tagName.toLowerCase()} class="${el.className.slice(0, 80)}">`);
              }
              for (const b of document.querySelectorAll('button, [role=menuitem], [role=tab]')) {
                const t = (b.getAttribute('aria-label') || b.innerText || '').trim().replace(/\\s+/g, ' ');
                if (t) out.push(`${b.getAttribute('role') || 'button'}: ${t.slice(0, 60)}`);
              }
              return out.slice(0, 120);
            }"""
        )


def sign_out() -> None:
    """Delete the Power BI Window's profile, and with it the Power BI session."""
    shutil.rmtree(profile_dir(), ignore_errors=True)
