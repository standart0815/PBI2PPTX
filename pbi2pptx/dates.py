"""Date Rules: named dates worked out when the Export runs (DESIGN.md, Date Filters)."""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum


class DateRule(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    START_OF_THIS_MONTH = "startOfThisMonth"
    START_OF_LAST_MONTH = "startOfLastMonth"
    END_OF_LAST_MONTH = "endOfLastMonth"
    START_OF_THIS_YEAR = "startOfThisYear"
    START_OF_LAST_YEAR = "startOfLastYear"
    END_OF_LAST_YEAR = "endOfLastYear"

    def on(self, today: date) -> date:
        """The date this rule stands for when the Export starts on `today`."""
        start_of_month = today.replace(day=1)
        end_of_last_month = start_of_month - timedelta(days=1)
        return {
            DateRule.TODAY: today,
            DateRule.YESTERDAY: today - timedelta(days=1),
            DateRule.START_OF_THIS_MONTH: start_of_month,
            DateRule.START_OF_LAST_MONTH: end_of_last_month.replace(day=1),
            DateRule.END_OF_LAST_MONTH: end_of_last_month,
            DateRule.START_OF_THIS_YEAR: date(today.year, 1, 1),
            DateRule.START_OF_LAST_YEAR: date(today.year - 1, 1, 1),
            DateRule.END_OF_LAST_YEAR: date(today.year - 1, 12, 31),
        }[self]


# --- Dates on slides, in the Render Language ("de" or "en") -------------------------------------

RULE_NAMES = {
    "de": {
        DateRule.TODAY: "Heute",
        DateRule.YESTERDAY: "Gestern",
        DateRule.START_OF_THIS_MONTH: "Anfang dieses Monats",
        DateRule.START_OF_LAST_MONTH: "Anfang letzten Monats",
        DateRule.END_OF_LAST_MONTH: "Ende letzten Monats",
        DateRule.START_OF_THIS_YEAR: "Anfang dieses Jahres",
        DateRule.START_OF_LAST_YEAR: "Anfang letzten Jahres",
        DateRule.END_OF_LAST_YEAR: "Ende letzten Jahres",
    },
    "en": {
        DateRule.TODAY: "Today",
        DateRule.YESTERDAY: "Yesterday",
        DateRule.START_OF_THIS_MONTH: "Start of this month",
        DateRule.START_OF_LAST_MONTH: "Start of last month",
        DateRule.END_OF_LAST_MONTH: "End of last month",
        DateRule.START_OF_THIS_YEAR: "Start of this year",
        DateRule.START_OF_LAST_YEAR: "Start of last year",
        DateRule.END_OF_LAST_YEAR: "End of last year",
    },
}
OPEN_ENDS = {"de": ("ab", "bis"), "en": ("from", "until")}


def date_text(day: date, language: str) -> str:
    """01.01.2026 (Deutsch) or 01/01/2026 (English)."""
    return f"{day:%d.%m.%Y}" if language == "de" else f"{day:%m/%d/%Y}"


def range_text(start: str | None, end: str | None, language: str) -> str:
    """Two ends already written out: "A – B", "ab A" or "bis B" ("from A", "until B")."""
    if start and end:
        return f"{start} – {end}"
    after, before = OPEN_ENDS[language]
    return f"{after} {start}" if start else f"{before} {end}"
