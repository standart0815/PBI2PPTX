"""Taking over the filters a User set on a page, for "Add current page" (DESIGN.md, Building a Selection).

The Power BI Window collects what the Filter Pane and the slicers show; this module decides what
becomes a Filter. Only "column is one of these text values" is taken over, with exact table and
column names. Everything else is left out with a reason the interface shows. A Filter is never
taken over incomplete.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import power_bi_ui as ui
from .page_url import Filter

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
    kind: str  # "list", "dropdown" or "range"
    ticked: tuple = ()  # list: the ticked values
    select_all: str = ""  # list: aria-checked of "Select all" ("true", "false", "mixed", "" if none)
    dropdown_text: str = ""  # dropdown: what it shows
    scrollable: bool = False  # list: more values than are in the page


@dataclass(frozen=True)
class LeftOut:
    what: str
    reason: str


@dataclass
class TakeOver:
    filters: list = field(default_factory=list)  # [Filter]
    left_out: list = field(default_factory=list)  # [LeftOut]


def split_field(text: str) -> tuple | None:
    """'"financials"[Country]' → ("financials", "Country")."""
    match = _FIELD.match(text.strip())
    return (match["table"], match["column"]) if match else None


def looks_like_number_or_date(value: str) -> bool:
    return bool(_NUMBER_OR_DATE.fullmatch(value)) and any(c.isdigit() for c in value)


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
        if slicer.kind == "range":
            result.left_out.append(LeftOut(what, "ranges aren't supported"))
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
    return result
