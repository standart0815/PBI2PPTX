"""Page URLs, Power BI App links and Filters in Power BI's URL filter syntax."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Optional, Sequence
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from .dates import RULE_NAMES, DateRule, date_text, range_text

POWER_BI = "https://app.powerbi.com/"

# Power BI's limits for URL filters: conditions joined by "and", and the length of the address.
MAX_CONDITIONS = 10
MAX_ADDRESS_LENGTH = 2000

_PAGE_URL = re.compile(
    r"^https://app\.powerbi\.com/groups/(?P<workspace>[^/]+)/(?:apps/(?P<app>[^/]+)/)?"
    r"reports/(?P<report>[0-9a-f-]{36})/(?P<page>[^/?#]+)",
    re.IGNORECASE,
)
_APP_LINK = re.compile(r"^https://app\.powerbi\.com/Redirect\?", re.IGNORECASE)


class ReachedThrough(str, Enum):
    WORKSPACE = "Workspace"
    MY_WORKSPACE = "My workspace"
    POWER_BI_APP = "Power BI App"


@dataclass(frozen=True)
class PageUrl:
    """The address of one Report Page, reduced to what identifies it."""

    workspace: str  # "me" for My workspace and for Power BI Apps
    app: Optional[str]
    report: str
    page: str
    ctid: Optional[str] = None  # the tenant, needed for guest access

    @property
    def reached_through(self) -> ReachedThrough:
        if self.app:
            return ReachedThrough.POWER_BI_APP
        return ReachedThrough.MY_WORKSPACE if self.workspace == "me" else ReachedThrough.WORKSPACE

    @property
    def url(self) -> str:
        path = f"groups/{self.workspace}/" + (f"apps/{self.app}/" if self.app else "") + f"reports/{self.report}/{self.page}"
        return POWER_BI + path + (f"?ctid={self.ctid}" if self.ctid else "")

    def with_filters(self, filters: Sequence["Filter"]) -> str:
        if not filters:
            return self.url
        scheme, netloc, path, query, fragment = urlsplit(self.url)
        params = dict(parse_qsl(query))
        params["filter"] = filter_expression(filters)
        return urlunsplit((scheme, netloc, path, urlencode(params, quote_via=quote), fragment))


def parse_page_url(url: str) -> PageUrl:
    match = _PAGE_URL.match(url.strip())
    if not match:
        raise ValueError(f"Not a Power BI report page URL: {url}")
    query = dict(parse_qsl(urlsplit(url.strip()).query))
    return PageUrl(match["workspace"], match["app"], match["report"], match["page"], query.get("ctid"))


def is_app_link(url: str) -> bool:
    """A shared link such as /Redirect?action=OpenApp&appId=…, which only Power BI can resolve to a page."""
    if not _APP_LINK.match(url.strip()):
        return False
    query = dict(parse_qsl(urlsplit(url.strip()).query))
    return query.get("action", "").lower() == "openapp" and "appId" in query


@dataclass(frozen=True)
class Filter:
    """A condition on a report field, applied on top of the Default State."""

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

    def to_json(self) -> dict:
        return {"table": self.table, "column": self.column, "values": list(self.values)}

    @classmethod
    def from_json(cls, data: dict) -> "Filter":
        table, column = str(data.get("table", "")).strip(), str(data.get("column", "")).strip()
        values = tuple(str(v).strip() for v in data.get("values", []) if str(v).strip())
        if not (table and column and values):
            raise ValueError("A Filter needs a table, a column and at least one value")
        return cls(table, column, values)

    def on(self, today: date) -> "Filter":
        return self

    def conditions(self) -> list:
        target = f"{_escape_name(self.table)}/{_escape_name(self.column)}"
        if len(self.values) == 1:
            return [f"{target} eq {_literal(self.values[0])}"]
        return [f"{target} in ({','.join(_literal(v) for v in self.values)})"]


@dataclass(frozen=True)
class DateFilter:
    """A Filter on a date column with a from (start) and/or a to (end), both inclusive.

    Each end is a fixed date or a Date Rule. Rules are worked out with on() when the Export starts;
    only a Date Filter with fixed dates goes into a page address.
    """

    table: str
    column: str
    start: date | DateRule | None = None
    end: date | DateRule | None = None

    def to_json(self) -> dict:
        def end(value):
            if value is None:
                return None
            return {"rule": value.value} if isinstance(value, DateRule) else {"date": value.isoformat()}

        return {"table": self.table, "column": self.column, "from": end(self.start), "to": end(self.end)}

    @classmethod
    def from_json(cls, data: dict) -> "DateFilter":
        table, column = str(data.get("table", "")).strip(), str(data.get("column", "")).strip()
        if not (table and column):
            raise ValueError("A Filter needs a table and a column")
        start, end = _date_end(data.get("from")), _date_end(data.get("to"))
        if start is None and end is None:
            raise ValueError("A Date Filter needs a from or a to")
        if isinstance(start, date) and isinstance(end, date) and start > end:
            raise ValueError(f"In the Date Filter on {column}, from is after to")
        return cls(table, column, start, end)

    def __str__(self) -> str:
        return f"{self.table}/{self.column}: {self.text('en')}"

    def text(self, language: str, today: date | None = None) -> str:
        """The range in the Render Language ("de"/"en"). With `today`, rules show their date and name."""

        def end(value):
            if value is None:
                return None
            if not isinstance(value, DateRule):
                return date_text(value, language)
            name = RULE_NAMES[language][value]
            return f"{date_text(value.on(today), language)} ({name})" if today else name

        return range_text(end(self.start), end(self.end), language)

    @property
    def empty(self) -> bool:
        """A fixed range whose from is after its to; rules can produce one (from Start of this month to Yesterday, on the 1st)."""
        return isinstance(self.start, date) and isinstance(self.end, date) and self.start > self.end

    def on(self, today: date) -> "DateFilter":
        def fixed(end):
            return end.on(today) if isinstance(end, DateRule) else end

        return DateFilter(self.table, self.column, fixed(self.start), fixed(self.end))

    def conditions(self) -> list:
        # The end day counts in full, even on columns that store a time: "before the next day".
        target = f"{_escape_name(self.table)}/{_escape_name(self.column)}"
        parts = []
        if self.start is not None:
            parts.append(f"{target} ge {self.start.isoformat()}")
        if self.end is not None:
            parts.append(f"{target} lt {(self.end + timedelta(days=1)).isoformat()}")
        return parts


def _date_end(data) -> date | DateRule | None:
    if not data:
        return None
    if "rule" in data:
        try:
            return DateRule(data["rule"])
        except ValueError:
            raise ValueError(f"unknown Date Rule: {data['rule']}") from None
    try:
        return date.fromisoformat(str(data.get("date", "")))
    except ValueError:
        raise ValueError(f"not a date: {data.get('date')}") from None


def filter_from_json(data: dict) -> "Filter | DateFilter":
    """A Filter from the Saved Selection or the interface: values, or a date range ("from"/"to")."""
    if not isinstance(data, dict):
        raise ValueError("A Filter must be an object")
    return DateFilter.from_json(data) if "from" in data or "to" in data else Filter.from_json(data)


def _escape_name(name: str) -> str:
    # Power BI URL filters encode special characters in table/column names as _xHHHH_.
    return "".join(c if c.isalnum() or c == "_" else f"_x{ord(c):04X}_" for c in name)


def _literal(value: str) -> str:
    # Known limitation: a value made only of digits is sent as a number, which fails on text columns.
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return value
    return "'" + value.replace("'", "''") + "'"


def filter_expression(filters: Sequence) -> str:
    return " and ".join(c for f in filters for c in f.conditions())


def condition_count(filters: Sequence) -> int:
    """Power BI's count: one per Filter, and one per end of a Date Filter."""
    return sum(len(f.conditions()) for f in filters)
