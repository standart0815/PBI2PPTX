"""The Export end to end: window service + fake Power BI page + sample template → Deck."""

import asyncio
import io

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from pbi2pptx.export import EntryState, Exporter, ExportRefused, ExportState
from pbi2pptx.page_url import Filter
from pbi2pptx.selection import Entry, Selection
from tests.test_power_bi_window import MISSING, REPORT, WS_PAGE
from tests.test_window_service import service_for

APP_PAGE = f"https://app.powerbi.com/groups/me/apps/a1a1a1a1-0000-0000-0000-000000000005/reports/{REPORT}/aaaa0000000000000002"
GERMANY = Filter.parse("financials/Country=Germany")
TYPO = Filter.parse("financials/Land=Germany")


def entry(url, title, *filters):
    return Entry(url, title, "Beispielbericht", title, list(filters))


async def run_export(tmp_path, selection, template, before=None):
    service, _ = service_for(tmp_path)
    await service.start()
    exporter = Exporter(service)
    try:
        if before:
            await before(service)
        exporter.start(selection, template)
        while exporter.running:
            await asyncio.sleep(0.2)
        return exporter, service.language
    finally:
        await service.stop()


def slides(deck: bytes):
    return list(Presentation(io.BytesIO(deck)).slides)


def text_of(slide) -> str:
    return " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)


def test_exports_every_entry_and_turns_failures_into_error_slides(tmp_path, sample_template):
    selection = Selection(
        "Monthly pack: EMEA",
        [
            entry(WS_PAGE, "Umsatz"),
            entry(WS_PAGE, "Umsatz Deutschland", GERMANY),
            entry(WS_PAGE, "Umsatz mit Tippfehler", TYPO),
            entry(MISSING, "Gelöschte Seite"),
            entry(APP_PAGE, "Regionen (App)", GERMANY),
        ],
    )
    exporter, _ = asyncio.run(run_export(tmp_path, selection, sample_template.read_bytes()))

    progress = exporter.progress
    assert progress.state is ExportState.DONE
    assert [e.state for e in progress.entries] == [
        EntryState.CAPTURED,
        EntryState.CAPTURED,
        EntryState.ERROR_SLIDE,
        EntryState.ERROR_SLIDE,
        EntryState.CAPTURED,
    ]
    assert "Power BI did not apply: financials/Land = Germany" in progress.entries[2].message

    file_name, deck = exporter.deck()
    assert file_name.startswith("Monthly pack EMEA ") and file_name.endswith(".pptx")
    deck_slides = slides(deck)
    assert [s.shapes.title.text for s in deck_slides] == [e.slide_title for e in selection.entries]
    pictures = [any(sh.shape_type == MSO_SHAPE_TYPE.PICTURE for sh in s.shapes) for s in deck_slides]
    assert pictures == [True, True, False, False, True]
    assert "Power BI hat diese Filter nicht angewendet: financials/Land = Germany" in text_of(deck_slides[2])
    assert "Keine Berichtsseite unter dieser Adresse" in text_of(deck_slides[3])


def test_hidden_filter_pane_is_exported_but_marked_not_verified(tmp_path, sample_template):
    async def hide_pane(service):
        await service._window.page.evaluate("() => localStorage.setItem('fake-no-pane', '1')")

    selection = Selection("Pack", [entry(WS_PAGE, "Umsatz Deutschland", GERMANY)])
    exporter, _ = asyncio.run(run_export(tmp_path, selection, sample_template.read_bytes(), before=hide_pane))
    (item,) = exporter.progress.entries
    assert item.state is EntryState.NOT_VERIFIED
    (slide,) = slides(exporter.deck()[1])
    assert "Filter-Prüfung: nicht möglich" in slide.notes_slide.notes_text_frame.text


def test_render_language_reopens_the_window_in_that_language(tmp_path, sample_template):
    selection = Selection("Pack", [entry(WS_PAGE, "Sales", TYPO)], render_language="en-US")
    exporter, language = asyncio.run(run_export(tmp_path, selection, sample_template.read_bytes()))
    assert language == "en-US"
    (slide,) = slides(exporter.deck()[1])
    assert "Power BI did not apply these Filters" in text_of(slide)  # Error Slide in English


def test_cancel_stops_without_a_deck(tmp_path, sample_template):
    async def go():
        service, _ = service_for(tmp_path)
        await service.start()
        exporter = Exporter(service)
        try:
            exporter.start(Selection("Pack", [entry(WS_PAGE, "A"), entry(WS_PAGE, "B"), entry(WS_PAGE, "C")]), sample_template.read_bytes())
            exporter.cancel()
            while exporter.running:
                await asyncio.sleep(0.2)
            return exporter
        finally:
            await service.stop()

    exporter = asyncio.run(go())
    assert exporter.progress.state is ExportState.CANCELLED
    assert exporter.deck() is None


def test_refuses_to_start_without_what_it_needs(tmp_path, sample_template):
    async def go():
        service, _ = service_for(tmp_path)
        exporter = Exporter(service)
        with pytest.raises(ExportRefused, match="template"):
            exporter.start(Selection("Pack", [entry(WS_PAGE, "A")]), None)
        with pytest.raises(ExportRefused, match="no Entries"):
            exporter.start(Selection("Pack", []), sample_template.read_bytes())
        # The window isn't open: the Export starts, then fails with a message for the User.
        exporter.start(Selection("Pack", [entry(WS_PAGE, "A")]), sample_template.read_bytes())
        with pytest.raises(ExportRefused, match="already running"):
            exporter.start(Selection("Pack", [entry(WS_PAGE, "A")]), sample_template.read_bytes())
        while exporter.running:
            await asyncio.sleep(0.1)
        return exporter.progress

    progress = asyncio.run(go())
    assert progress.state is ExportState.FAILED and "isn't open" in progress.error


def test_show_filters_puts_a_filter_box_on_filtered_slides(tmp_path, sample_template):
    selection = Selection("Pack", [entry(WS_PAGE, "DE", GERMANY), entry(WS_PAGE, "All")], show_filters=True)
    exporter, _ = asyncio.run(run_export(tmp_path, selection, sample_template.read_bytes()))
    with_filters, without = slides(exporter.deck()[1])
    (filter_box,) = [s for s in with_filters.shapes if s.name == "Filter Box"]
    assert filter_box.text_frame.text.splitlines() == ["Filter", "Country: Germany"]
    assert all(s.name != "Filter Box" for s in without.shapes)
