import json

import pytest

from pbi2pptx.page_url import Filter
from pbi2pptx.selection import MAX_ENTRIES, Entry, Selection, SelectionError, safe_file_name

PAGE = "https://app.powerbi.com/groups/2b2b2b2b-0000-0000-0000-000000000002/reports/11111111-0000-0000-0000-000000000001/aaaa0000000000000001"
APP_PAGE = "https://app.powerbi.com/groups/me/apps/a1a1a1a1-0000-0000-0000-000000000005/reports/11111111-0000-0000-0000-000000000001/aaaa0000000000000001?ctid=t-1"


def selection(**overrides) -> Selection:
    entries = [
        Entry(PAGE, "Umsatz", "Beispielbericht", "Umsatz gesamt"),
        Entry(APP_PAGE, "Umsatz", "Beispielbericht", "Umsatz DE", [Filter("financials", "Country", ("Germany",))]),
    ]
    return Selection(**{"name": "Monthly pack EMEA", "entries": entries, **overrides})


def test_saved_selection_round_trips():
    original = selection(render_language="en-US", slide_layout="Tabelle", show_filters=True)
    reopened = Selection.loads(original.dumps())
    assert reopened == original
    assert reopened.entries[1].page_url.endswith("?ctid=t-1")  # the tenant survives


def test_file_carries_its_schema_version_and_readable_text():
    text = selection().dumps()
    data = json.loads(text)
    assert (data["schemaVersion"], data["app"]) == (1, "PBI2PPTX")
    assert data["entries"][1]["filters"] == [{"table": "financials", "column": "Country", "values": ["Germany"]}]
    assert "Umsatz" in text  # umlauts and names stay readable, not \u-escaped


def test_file_name_comes_from_the_selection_name():
    assert selection().file_name() == "Monthly pack EMEA.json"
    assert safe_file_name('Q3: EMEA/DACH "final"') == "Q3 EMEA DACH final"
    assert safe_file_name("  ...  ") == "Untitled Selection"


def test_page_urls_are_stored_without_noise():
    data = selection().to_json()
    data["entries"][0]["pageUrl"] = PAGE + "?experience=power-bi&filter=x"
    assert Selection.from_json(data).entries[0].page_url == PAGE


def test_missing_titles_fall_back_to_the_page_name():
    data = selection().to_json()
    data["entries"][0]["slideTitle"] = "  "
    assert Selection.from_json(data).entries[0].slide_title == "Umsatz"


@pytest.mark.parametrize(
    "text, message",
    [
        ("not json", "not valid JSON"),
        ('{"hello": "world"}', "not a Saved Selection"),
        ('{"schemaVersion": 3, "entries": []}', "newer PBI2PPTX"),
        ('{"schemaVersion": 1, "entries": [{"pageUrl": "https://example.com"}]}', "Entry 1 has no valid Power BI page address"),
        (
            json.dumps({"schemaVersion": 1, "entries": [{"pageUrl": PAGE, "filters": [{"table": "t", "values": ["x"]}]}]}),
            "Entry 1: A Filter needs a table, a column and at least one value",
        ),
    ],
)
def test_unreadable_files_are_refused_with_a_reason(text, message):
    with pytest.raises(SelectionError, match=message):
        Selection.loads(text)


def test_more_than_the_export_limit_is_refused():
    data = selection().to_json()
    data["entries"] = [data["entries"][0]] * (MAX_ENTRIES + 1)
    with pytest.raises(SelectionError, match=f"at most {MAX_ENTRIES}"):
        Selection.from_json(data)


def test_unknown_render_language_falls_back_to_german():
    data = selection().to_json()
    data["renderLanguage"] = "fr-FR"
    assert Selection.from_json(data).render_language == "de-DE"


def test_older_files_without_the_filter_setting_show_no_filters():
    data = selection().to_json()
    del data["showFilters"]
    assert Selection.from_json(data).show_filters is False


# --- Date Filters (format version 2) ------------------------------------------------------------

from datetime import date  # noqa: E402

from pbi2pptx.dates import DateRule  # noqa: E402
from pbi2pptx.page_url import DateFilter  # noqa: E402

YEAR_TO_DATE = DateFilter("Calendar", "Date", DateRule.START_OF_THIS_YEAR, DateRule.TODAY)


def test_date_filters_round_trip_in_format_version_2():
    original = selection()
    original.entries[0].filters = [YEAR_TO_DATE, DateFilter("Calendar", "Date", end=date(2026, 10, 19))]
    data = json.loads(original.dumps())
    assert data["schemaVersion"] == 2
    assert data["entries"][0]["filters"] == [
        {"table": "Calendar", "column": "Date", "from": {"rule": "startOfThisYear"}, "to": {"rule": "today"}},
        {"table": "Calendar", "column": "Date", "from": None, "to": {"date": "2026-10-19"}},
    ]
    assert Selection.loads(original.dumps()) == original


def test_files_without_date_filters_stay_readable_for_older_versions():
    assert json.loads(selection().dumps())["schemaVersion"] == 1


@pytest.mark.parametrize(
    "date_filter, message",
    [
        ({"from": None, "to": None}, "needs a from or a to"),
        ({"from": {"rule": "nextFullMoon"}}, "unknown Date Rule"),
        ({"from": {"date": "19.10.2026"}}, "not a date"),
        ({"from": {"date": "2026-10-20"}, "to": {"date": "2026-10-19"}}, "from is after to"),
    ],
)
def test_broken_date_filters_are_refused(date_filter, message):
    entry = {"pageUrl": PAGE, "filters": [{"table": "Calendar", "column": "Date", **date_filter}]}
    with pytest.raises(SelectionError, match=f"Entry 1: .*{message}"):
        Selection.from_json({"schemaVersion": 2, "entries": [entry]})


# --- Custom Image Area ------------------------------------------------------------------------

from pbi2pptx.selection import CustomImageArea  # noqa: E402


def test_custom_image_area_round_trips_in_cm():
    original = selection(image_area=CustomImageArea(1.5, 3.25, 28.0, 14.5))
    data = json.loads(original.dumps())
    assert data["imageArea"] == {"left": 1.5, "top": 3.25, "width": 28.0, "height": 14.5}
    assert data["schemaVersion"] == 1  # older versions read it, and use the layout's area
    assert Selection.loads(original.dumps()) == original
    assert original.image_area.box().left == 540_000  # 1.5 cm in EMU


def test_files_without_a_custom_image_area_use_the_layouts():
    data = selection().to_json()
    assert data["imageArea"] is None
    del data["imageArea"]
    assert Selection.from_json(data).image_area is None


@pytest.mark.parametrize(
    "area",
    [{"left": 1, "top": 2, "width": 0, "height": 3}, {"left": -1, "top": 2, "width": 3, "height": 3}, {"left": "1"}, [1, 2, 3, 4]],
)
def test_broken_custom_image_areas_are_refused(area):
    data = selection().to_json()
    data["imageArea"] = area
    with pytest.raises(SelectionError, match="picture area"):
        Selection.from_json(data)
