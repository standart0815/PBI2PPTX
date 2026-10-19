"""Page URLs, Power BI App links and Filters in Power BI's URL filter syntax."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

POWER_BI = "https://app.powerbi.com/"

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


def _escape_name(name: str) -> str:
    # Power BI URL filters encode special characters in table/column names as _xHHHH_.
    return "".join(c if c.isalnum() or c == "_" else f"_x{ord(c):04X}_" for c in name)


def _literal(value: str) -> str:
    # Known limitation: a value made only of digits is sent as a number, which fails on text columns.
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return value
    return "'" + value.replace("'", "''") + "'"


def filter_expression(filters: Sequence[Filter]) -> str:
    parts = []
    for f in filters:
        target = f"{_escape_name(f.table)}/{_escape_name(f.column)}"
        if len(f.values) == 1:
            parts.append(f"{target} eq {_literal(f.values[0])}")
        else:
            parts.append(f"{target} in ({','.join(_literal(v) for v in f.values)})")
    return " and ".join(parts)
