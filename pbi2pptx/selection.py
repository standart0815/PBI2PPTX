"""The Selection, its Entries, and the Saved Selection file.

The interface holds the Selection while the User works on it. Reading and writing the Saved
Selection JSON happens only here, so the Export reads exactly what the User saved.

File format (schemaVersion 1, or 2 when an Entry has a Date Filter, so that older versions refuse
only the files they can't read):

    {
      "schemaVersion": 1,
      "app": "PBI2PPTX",
      "name": "Monthly pack EMEA",
      "renderLanguage": "de-DE",
      "slideLayout": null,
      "showFilters": false,            # a Filter Box on slides whose Entry has Filters
      "imageArea": null,               # or a Custom Image Area in cm: {"left", "top", "width", "height"}
      "entries": [
        {
          "pageUrl": "https://app.powerbi.com/groups/…/reports/…/…",
          "pageName": "Example",          # snapshot, for display
          "reportName": "Example",        # snapshot, for display
          "slideTitle": "Example",
          "filters": [
            {"table": "financials", "column": "Country", "values": ["Germany"]},
            {"table": "Calendar", "column": "Date", "from": {"rule": "startOfThisYear"}, "to": {"date": "2026-10-19"}}
          ]
        }
      ]
    }
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .page_url import DateFilter, filter_from_json, parse_page_url
from .template import EMU_PER_CM, Box

SCHEMA_VERSION = 2  # the newest format this version reads and writes
MAX_ENTRIES = 50
RENDER_LANGUAGES = ("de-DE", "en-US")
DEFAULT_NAME = "Untitled Selection"


class SelectionError(ValueError):
    """A Saved Selection that can't be read, with a message for the User."""


@dataclass(frozen=True)
class CustomImageArea:
    """The Custom Image Area, in cm from the slide's top-left corner."""

    left: float
    top: float
    width: float
    height: float

    def to_json(self) -> dict:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}

    @classmethod
    def from_json(cls, data) -> "CustomImageArea":
        if not isinstance(data, dict):
            raise SelectionError("The picture area is not an object")
        values = [data.get(k) for k in ("left", "top", "width", "height")]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            raise SelectionError("The picture area needs a left, top, width and height in cm")
        left, top, width, height = (round(float(v), 2) for v in values)
        if left < 0 or top < 0 or width <= 0 or height <= 0:
            raise SelectionError("The picture area needs a width and a height, and starts on the slide")
        return cls(left, top, width, height)

    def box(self) -> Box:
        return Box(*(round(v * EMU_PER_CM) for v in (self.left, self.top, self.width, self.height)))


@dataclass
class Entry:
    page_url: str
    page_name: str
    report_name: str
    slide_title: str
    filters: list = field(default_factory=list)  # [Filter | DateFilter]

    def to_json(self) -> dict:
        return {
            "pageUrl": self.page_url,
            "pageName": self.page_name,
            "reportName": self.report_name,
            "slideTitle": self.slide_title,
            "filters": [f.to_json() for f in self.filters],
        }

    @classmethod
    def from_json(cls, data: dict, position: int) -> "Entry":
        where = f"Entry {position}"
        if not isinstance(data, dict):
            raise SelectionError(f"{where} is not an object")
        try:
            page_url = parse_page_url(str(data.get("pageUrl", ""))).url
        except ValueError:
            raise SelectionError(f"{where} has no valid Power BI page address") from None
        page_name = str(data.get("pageName") or "").strip() or page_url.rsplit("/", 1)[-1].split("?")[0]
        try:
            filters = [filter_from_json(f) for f in data.get("filters", [])]
        except (ValueError, AttributeError) as e:
            raise SelectionError(f"{where}: {e}") from None
        return cls(
            page_url=page_url,
            page_name=page_name,
            report_name=str(data.get("reportName") or "").strip(),
            slide_title=str(data.get("slideTitle") or "").strip() or page_name,
            filters=filters,
        )


@dataclass
class Selection:
    name: str = DEFAULT_NAME
    entries: list = field(default_factory=list)  # [Entry]
    render_language: str = "de-DE"
    slide_layout: str | None = None
    show_filters: bool = False
    image_area: CustomImageArea | None = None  # None: the Slide Layout's Image Area

    def to_json(self) -> dict:
        dated = any(isinstance(f, DateFilter) for e in self.entries for f in e.filters)
        return {
            "schemaVersion": 2 if dated else 1,
            "app": "PBI2PPTX",
            "name": self.name,
            "renderLanguage": self.render_language,
            "slideLayout": self.slide_layout,
            "showFilters": self.show_filters,
            "imageArea": self.image_area.to_json() if self.image_area else None,
            "entries": [e.to_json() for e in self.entries],
        }

    @classmethod
    def from_json(cls, data: dict) -> "Selection":
        if not isinstance(data, dict):
            raise SelectionError("This is not a Saved Selection")
        version = data.get("schemaVersion")
        if version not in (1, SCHEMA_VERSION):
            if isinstance(version, int) and version > SCHEMA_VERSION:
                raise SelectionError("This Saved Selection comes from a newer PBI2PPTX. Please update PBI2PPTX.")
            raise SelectionError("This is not a Saved Selection")
        entries = data.get("entries", [])
        if not isinstance(entries, list):
            raise SelectionError("The Saved Selection has no list of Entries")
        if len(entries) > MAX_ENTRIES:
            raise SelectionError(f"A Selection holds at most {MAX_ENTRIES} Entries; this one has {len(entries)}")
        language = data.get("renderLanguage", "de-DE")
        return cls(
            name=str(data.get("name") or "").strip() or DEFAULT_NAME,
            entries=[Entry.from_json(e, i) for i, e in enumerate(entries, 1)],
            render_language=language if language in RENDER_LANGUAGES else "de-DE",
            slide_layout=(str(data["slideLayout"]).strip() or None) if data.get("slideLayout") else None,
            show_filters=data.get("showFilters") is True,
            image_area=CustomImageArea.from_json(data["imageArea"]) if data.get("imageArea") is not None else None,
        )

    # --- The file ----------------------------------------------------------------------------

    def file_name(self) -> str:
        return f"{safe_file_name(self.name)}.json"

    def dumps(self) -> str:
        return json.dumps(self.to_json(), indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def loads(cls, text: str) -> "Selection":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise SelectionError("This file isn't a Saved Selection (not valid JSON)") from None
        return cls.from_json(data)


def safe_file_name(name: str) -> str:
    """A file name that works on Windows and macOS: no path or reserved characters."""
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name).strip(" .")
    return re.sub(r"\s+", " ", cleaned)[:120] or DEFAULT_NAME
