"""Taking over the filters a User set on a page, for "Add current page" (DESIGN.md, Building a Selection).

The Power BI Window collects what the Filter Pane and the slicers show; this module decides what
becomes a Filter. Taken over are "column is one of these text values", and date ranges from date
cards and date slicers, which become one Date Filter with fixed dates per field. Table and column
names are exact. Everything else is left out with a reason the interface shows. A Filter is never
taken over incomplete.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import power_bi_ui as ui
from .page_url import DateFilter, Filter

_FIELD = re.compile(r"""^["']?(?P<table>.+?)["']?\[(?P<column>.+)\]$""")
_NUMBER_OR_DATE = re.compile(r"[\d\s.,:/+\-]+")


@dataclass(frozen=True)
class FilterCard:
    """One Filter Pane card as read from the page."""

    field: str  # e.g. '"financials"[Country]'
    condition: str  # e.g. 'ist Germany oder France'
    ticked: tuple = ()  # values read from the expanded card, when the condition was shortened


@dataclass(frozen=True)
class Slicer:
    """One slicer as read from the page."""

    column: str  # the header, e.g. "Discount Band"
    kind: str  # "list", "dropdown", "range", or "other" (e.g. relative dates)
    ticked: tuple = ()  # list: the ticked values
    select_all: str = ""  # list: aria-checked of "Select all" ("true", "false", "mixed", "" if none)
    dropdown_text: str = ""  # dropdown: what it shows
    scrollable: bool = False  # list: more values than are in the page
    labels: tuple = ()  # range: the aria-labels inside, which carry a date slicer's dates


@dataclass(frozen=True)
class LeftOut:
    what: str
    reason: str


@dataclass
class TakeOver:
    filters: list = field(default_factory=list)  # [Filter | DateFilter]
    left_out: list = field(default_factory=list)  # [LeftOut]


def split_field(text: str) -> tuple | None:
    """'"financials"[Country]' → ("financials", "Country")."""
    match = _FIELD.match(text.strip())
    return (match["table"], match["column"]) if match else None


def looks_like_number_or_date(value: str) -> bool:
    return bool(_NUMBER_OR_DATE.fullmatch(value)) and any(c.isdigit() for c in value)


def date_condition(condition: str) -> tuple | None:
    """A date card's condition as ("start" | "end", inclusive date): "ist vor 01.01.2014" → ("end", 31.12.2013)."""
    for prefixes, end, shift in (
        (ui.DATE_ON_OR_AFTER, "start", 0),
        (ui.DATE_AFTER, "start", 1),
        (ui.DATE_ON_OR_BEFORE, "end", 0),
        (ui.DATE_BEFORE, "end", -1),
    ):
        prefix = next((p for p in prefixes if condition.startswith(p)), None)
        if prefix is not None:
            day = ui.parse_shown_date(condition[len(prefix) :])
            return (end, day + timedelta(days=shift)) if day else None
    return None


def slicer_dates(labels: tuple) -> tuple | None:
    """A date slicer's (available first, available last, chosen first, chosen last), each (shown, date); None if not dates."""
    available, chosen = None, {}
    for label in labels:
        if match := re.search(ui.SLICER_AVAILABLE, label):
            available = (match["first"], match["last"])
        elif match := re.search(ui.SLICER_CHOSEN, label):
            chosen["start" if match["end"] in ui.SLICER_START else "end"] = match["date"].strip()
    shown = (*available, chosen.get("start"), chosen.get("end")) if available else ()
    days = tuple(ui.parse_shown_date(s) for s in shown if s)
    if len(days) != 4 or None in days:
        return None
    return tuple(zip(shown, days))


def _split_values(text: str) -> tuple:
    return tuple(v.strip() for v in re.split(ui.FILTER_CARD_VALUE_SEPARATORS, text) if v.strip())


def _add(result: TakeOver, table: str, column: str, values: tuple, what: str) -> None:
    if any(looks_like_number_or_date(v) for v in values):
        result.left_out.append(LeftOut(what, "numbers and dates aren't taken over"))
        return
    new = Filter(table, column, values)
    if new not in result.filters:
        result.filters.append(new)


def take_over(cards: list, slicers: list) -> TakeOver:
    result = TakeOver()
    tables = {}  # column → table, from the Filter Pane, for slicers
    ranges = {}  # (table, column) → [start, end]: every date setting on a field narrows one Date Filter

    def narrow(table: str, column: str, start: date | None, end: date | None) -> None:
        old = ranges.setdefault((table, column), [None, None])
        old[0] = max(d for d in (old[0], start) if d) if old[0] or start else None
        old[1] = min(d for d in (old[1], end) if d) if old[1] or end else None

    for card in cards:
        names = split_field(card.field)
        if names is None:
            continue
        table, column = names
        tables.setdefault(column, table)
        condition = " ".join(card.condition.split())
        what = f"{column} {condition}"
        if condition in ui.ALL_VALUES or condition.endswith(tuple(f" {v}" for v in ui.ALL_VALUES)):
            continue
        if condition.startswith(ui.CONDITION_IS_NOT):
            result.left_out.append(LeftOut(what, '"is not" isn\'t supported'))
            continue
        if dated := date_condition(condition):
            end, day = dated
            narrow(table, column, day if end == "start" else None, day if end == "end" else None)
            continue
        if condition.startswith(ui.CONDITION_RELATIVE):
            result.left_out.append(LeftOut(what, "relative dates aren't supported"))
            continue
        operator = next((p for p in ui.CONDITION_IS if condition.startswith(p)), None)
        if operator is None:
            result.left_out.append(LeftOut(what, 'only "is one of" is supported'))
            continue
        shown = condition[len(operator) :]
        if re.search(ui.ABBREVIATED, shown):
            if not card.ticked:
                result.left_out.append(LeftOut(what, "the list of values couldn't be read completely"))
                continue
            values = tuple(card.ticked)
        else:
            values = _split_values(shown)
        if values:
            _add(result, table, column, values, what)

    for slicer in slicers:
        what = f"Slicer {slicer.column}"
        if slicer.kind == "other":
            result.left_out.append(LeftOut(what, "this kind of slicer isn't supported (such as relative dates)"))
            continue
        if slicer.kind == "range":
            dates = slicer_dates(slicer.labels)
            if dates is None:
                result.left_out.append(LeftOut(what, "only date ranges are supported"))
                continue
            (_, first), (_, last), (shown_start, start), (shown_end, end) = dates
            start, end = (start if start > first else None), (end if end < last else None)
            if start is None and end is None:
                continue  # the whole available range: no filter, as with "Alle"
            table = tables.get(slicer.column)
            if table is None:
                result.left_out.append(LeftOut(f"{what} = {shown_start} – {shown_end}", "table unknown: add this Filter by hand"))
                continue
            narrow(table, slicer.column, start, end)
            continue
        if slicer.kind == "dropdown":
            text = slicer.dropdown_text.strip()
            if not text or text in ui.ALL_VALUES:
                continue
            if text in ui.MULTIPLE_SELECTIONS:
                result.left_out.append(LeftOut(what, "the list of values couldn't be read completely"))
                continue
            values = tuple(v.strip() for v in text.split(",") if v.strip())
        else:
            if slicer.select_all == "true" or not slicer.ticked:
                continue  # everything, or nothing chosen: no filter
            if slicer.scrollable:
                result.left_out.append(LeftOut(what, "the list is too long to read completely"))
                continue
            values = tuple(slicer.ticked)
        table = tables.get(slicer.column)
        if table is None:
            result.left_out.append(LeftOut(f"{what} = {', '.join(values)}", "table unknown: add this Filter by hand"))
            continue
        _add(result, table, slicer.column, values, f"{what} = {', '.join(values)}")
    result.filters.extend(DateFilter(table, column, start, end) for (table, column), (start, end) in ranges.items())
    return result
