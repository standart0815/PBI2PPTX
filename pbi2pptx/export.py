"""The Export: captures every Entry of a Selection and builds the Deck.

One Export at a time. It runs in the background, holds the Power BI Window (or, for a Hidden
Export, an invisible browser) for its whole duration, reports progress per Entry, and can be cancelled between Entries. Page Images live in
a temporary folder that is deleted when the Export ends; the Deck stays in memory until it is
downloaded, a new Export starts, or an hour has passed (DESIGN.md, Data handling).
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Callable

from .dates import date_text
from .deck import CapturedEntry, build_deck
from .page_url import MAX_ADDRESS_LENGTH, MAX_CONDITIONS, DateFilter, condition_count, parse_page_url
from .power_bi_window import FilterCheck, FiltersNotApplied, NotAReportPage
from .selection import Selection, safe_file_name
from .window_service import WindowNotOpen, WindowService

DECK_KEPT_SECONDS = 3600
log = logging.getLogger("pbi2pptx.export")

# Reasons on Error Slides and notes, in the Render Language.
REASONS = {
    "de": {
        "not_applied": "Power BI hat diese Filter nicht angewendet: {filters}. Bitte Tabellen- und Spaltennamen prüfen.",
        "no_page": "Keine Berichtsseite unter dieser Adresse (gelöscht oder kein Zugriff?).",
        "failed": "Die Seite konnte nicht erfasst werden: {detail}",
        "not_verified": "nicht möglich – der Bericht blendet den Filterbereich aus",
        "empty_range": "Der Datumsfilter {filter} ist leer: von {start} liegt nach bis {end}.",
        "too_many": "Zu viele Filterbedingungen für Power BI: {count}, erlaubt sind höchstens {max}. Ein Datumsfilter mit von und bis zählt doppelt.",
        "too_long": "Die Seitenadresse mit den Filtern ist zu lang für Power BI: {length} Zeichen, erlaubt sind etwa {max}.",
    },
    "en": {
        "not_applied": "Power BI did not apply these Filters: {filters}. Please check the table and column names.",
        "no_page": "No report page at this address (deleted, or no access?).",
        "failed": "The page could not be captured: {detail}",
        "not_verified": "not possible – the report hides its filter pane",
        "empty_range": "The Date Filter {filter} is empty: from {start} is after to {end}.",
        "too_many": "Too many filter conditions for Power BI: {count}, at most {max} are allowed. A Date Filter with from and to counts as two.",
        "too_long": "The page address with its Filters is too long for Power BI: {length} characters, about {max} are allowed.",
    },
}


class ExportRefused(ValueError):
    """The Export can't start; the message tells the User why."""


class ExportState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


class EntryState(str, Enum):
    WAITING = "waiting"
    CAPTURING = "capturing"
    CAPTURED = "captured"
    NOT_VERIFIED = "not verified"  # captured, but the report hides its filter pane
    ERROR_SLIDE = "error slide"


@dataclass
class EntryProgress:
    title: str
    filters: list
    state: EntryState = EntryState.WAITING
    message: str = ""
    seconds: float = 0.0


@dataclass
class ExportProgress:
    state: ExportState = ExportState.IDLE
    entries: list = field(default_factory=list)  # [EntryProgress]
    phase: str = ""  # what the Export is doing right now, for the interface
    file_name: str = ""
    error: str = ""

    def to_json(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        for e in data["entries"]:
            e["state"] = e["state"].value
        return data


def filter_line(f, today: date, language: str) -> str:
    """A line of the Filter Box: "Country: Germany, France", "Date: 01.01.2026 – 19.10.2026"."""
    if isinstance(f, DateFilter):
        return f"{f.column}: {f.on(today).text(language)}"
    return f"{f.column}: {', '.join(f.values)}"


def filter_note(f, today: date, language: str) -> str:
    """A Filter in the speaker notes and on Error Slides, with its table and the Date Rules by name."""
    if isinstance(f, DateFilter):
        return f"{f.table}/{f.column}: {f.text(language, today)}"
    return str(f)


def _number(n: int, language: str) -> str:
    return f"{n:,}".replace(",", ".") if language == "de" else f"{n:,}"


class Exporter:
    def __init__(self, windows: WindowService, today: Callable[[], date] = date.today):
        self._windows = windows
        self._today = today  # the day the Export starts works out every Date Rule
        self.progress = ExportProgress()
        self._task: asyncio.Task | None = None
        self._cancel = False
        self._deck: bytes | None = None
        self._deck_made = 0.0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, selection: Selection, template: bytes | None, hidden: bool = False) -> None:
        if self.running:
            raise ExportRefused("An Export is already running.")
        if template is None:
            raise ExportRefused("Choose a template first.")
        if not selection.entries:
            raise ExportRefused("The Selection has no Entries.")
        self._deck, self._cancel = None, False
        self.progress = ExportProgress(
            ExportState.RUNNING,
            [EntryProgress(e.slide_title, [f.to_json() for f in e.filters]) for e in selection.entries],
            phase="Starting the hidden browser" if hidden else "Preparing the Power BI Window",
        )
        self._task = asyncio.create_task(self._run(selection, template, hidden))

    def cancel(self) -> None:
        self._cancel = True

    async def stop(self) -> None:
        if self.running:
            self._cancel = True
            self._task.cancel()
            try:
                await self._task
            except BaseException:  # noqa: BLE001 - shutting down
                pass

    def deck(self) -> tuple[str, bytes] | None:
        """The finished Deck, while it is kept."""
        if self._deck is None or time.monotonic() - self._deck_made > DECK_KEPT_SECONDS:
            self._deck = None
            return None
        return self.progress.file_name, self._deck

    async def _run(self, selection: Selection, template: bytes, hidden: bool) -> None:
        language = selection.render_language[:2]
        today = self._today()  # one day for the whole Export, even if it runs past midnight
        progress = self.progress
        try:
            async with self._windows.exclusive(selection.render_language, hidden) as window:
                with tempfile.TemporaryDirectory(prefix="pbi2pptx-") as folder:
                    captured = []
                    for index, (entry, item) in enumerate(zip(selection.entries, progress.entries)):
                        if self._cancel:
                            progress.state, progress.phase = ExportState.CANCELLED, ""
                            return
                        progress.phase = f"Capturing {index + 1} of {len(progress.entries)}: {entry.slide_title}"
                        item.state = EntryState.CAPTURING
                        result = await self._capture(window, entry, item, Path(folder) / f"{index:02d}.png", today, language)
                        if selection.show_filters:
                            result.filter_box = [filter_line(f, today, language) for f in entry.filters]
                        captured.append(result)
                    if self._cancel:
                        progress.state, progress.phase = ExportState.CANCELLED, ""
                        return
                    progress.phase = "Building the Deck"
                    file_name = f"{safe_file_name(selection.name)} {today.isoformat()}.pptx"
                    out = Path(folder) / file_name
                    await asyncio.to_thread(build_deck, template, captured, out, selection.slide_layout, language)
                    self._deck, self._deck_made = out.read_bytes(), time.monotonic()
            progress.state, progress.phase, progress.file_name = ExportState.DONE, "", file_name
            counts = {s: sum(1 for i in progress.entries if i.state is s) for s in EntryState}
            log.info(
                "Export done: %d captured, %d not verified, %d Error Slides",
                counts[EntryState.CAPTURED], counts[EntryState.NOT_VERIFIED], counts[EntryState.ERROR_SLIDE],
            )
        except WindowNotOpen as e:
            log.warning("Export not started: %s", e)
            progress.state, progress.phase, progress.error = ExportState.FAILED, "", str(e)
        except asyncio.CancelledError:
            progress.state, progress.phase = ExportState.CANCELLED, ""
            raise
        except Exception as e:  # noqa: BLE001 - shown in the interface, and logged for problem reports
            log.exception("Export failed")
            progress.state, progress.phase, progress.error = ExportState.FAILED, "", f"The Export failed: {e}"

    async def _capture(self, window, entry, item: EntryProgress, out: Path, today: date, language: str) -> CapturedEntry:
        started = time.monotonic()
        reasons = REASONS.get(language, REASONS["en"])
        notes = [filter_note(f, today, language) for f in entry.filters]
        result = CapturedEntry(entry.slide_title, entry.page_url, None, entry.report_name, notes)
        filters = [f.on(today) for f in entry.filters]
        if problem := self._impossible(parse_page_url(entry.page_url), filters, language, reasons):
            result.error, item.message = problem
            item.state = EntryState.ERROR_SLIDE
            return result
        try:
            report = await window.capture(parse_page_url(entry.page_url), filters, out)
            result.image = out
            if report.filters is FilterCheck.NOT_VERIFIABLE:
                result.filter_note = reasons["not_verified"]
                item.state, item.message = EntryState.NOT_VERIFIED, "Filter not verified: the report hides its filter pane."
            else:
                item.state = EntryState.CAPTURED
        except FiltersNotApplied as e:
            result.error = reasons["not_applied"].format(filters="; ".join(filter_note(f, today, language) for f in e.missing))
            item.state, item.message = EntryState.ERROR_SLIDE, f"Power BI did not apply: {'; '.join(str(f) for f in e.missing)}"
        except NotAReportPage:
            result.error = reasons["no_page"]
            item.state, item.message = EntryState.ERROR_SLIDE, "No report page at this address (deleted, or no access?)."
        except Exception as e:  # noqa: BLE001 - one failing page must not stop the Export
            log.exception("Capturing an Entry failed")
            detail = str(e).splitlines()[0] if str(e) else type(e).__name__
            result.error = reasons["failed"].format(detail=detail)
            item.state, item.message = EntryState.ERROR_SLIDE, f"Could not capture: {detail}"
        item.seconds = round(time.monotonic() - started, 1)
        return result

    @staticmethod
    def _impossible(page_url, filters: list, language: str, reasons: dict) -> tuple | None:
        """Why Power BI can't show this page as asked, before trying: (Error Slide text, interface message)."""
        english = REASONS["en"]
        for f in filters:
            if isinstance(f, DateFilter) and f.empty:
                field = f"{f.table}/{f.column}"
                start, end = (date_text(f.start, language), date_text(f.end, language))
                return (
                    reasons["empty_range"].format(filter=field, start=start, end=end),
                    english["empty_range"].format(filter=field, start=date_text(f.start, "en"), end=date_text(f.end, "en")),
                )
        count = condition_count(filters)
        if count > MAX_CONDITIONS:
            return (
                reasons["too_many"].format(count=count, max=MAX_CONDITIONS),
                english["too_many"].format(count=count, max=MAX_CONDITIONS),
            )
        length = len(page_url.with_filters(filters))
        if length > MAX_ADDRESS_LENGTH:
            return (
                reasons["too_long"].format(length=_number(length, language), max=_number(MAX_ADDRESS_LENGTH, language)),
                english["too_long"].format(length=_number(length, "en"), max=_number(MAX_ADDRESS_LENGTH, "en")),
            )
        return None
