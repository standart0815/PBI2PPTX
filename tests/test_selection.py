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
    original = selection(render_language="en-US", slide_layout="Tabelle")
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
        ('{"schemaVersion": 2, "entries": []}', "newer PBI2PPTX"),
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
