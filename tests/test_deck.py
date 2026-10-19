from datetime import datetime

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from pbi2pptx.deck import CapturedEntry, build_deck
from pbi2pptx.template import FOOTER_TYPES, TITLE_TYPES, Box, image_area
from tests.fixtures.samples import HEADER_BOTTOM, SLIDE_W

URL = "https://app.powerbi.com/groups/me/reports/0e0e0e0e-0000-0000-0000-000000000004/cacea11bd78861e6a8a2"


def _entries(pages):
    return [CapturedEntry(p.stem, URL, p, "Example", ["financials/Country = Germany"]) for p in pages] + [
        CapturedEntry("broken", URL, None, "Example", error="No report page at this address")
    ]


@pytest.mark.parametrize("layout_name", ["PBI Page", "PBI Page (Picture)"])
def test_page_slides_never_cover_header_or_footers(sample_template, sample_pages, tmp_path, layout_name):
    entries = _entries(sample_pages)
    prs = Presentation(build_deck(sample_template, entries, tmp_path / "deck.pptx", layout_name=layout_name))
    slides = list(prs.slides)
    assert len(slides) == len(entries)  # the template's cover slide is dropped

    header = Box(0, 0, SLIDE_W, HEADER_BOTTOM)
    for slide, entry in zip(slides, entries):
        assert slide.shapes.title.text == entry.title
        assert {ph.placeholder_format.type for ph in slide.placeholders} <= TITLE_TYPES | FOOTER_TYPES
        footers = [Box.of(ph) for ph in slide.placeholders if ph.placeholder_format.type in FOOTER_TYPES]
        assert len(footers) == 3
        pictures = [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
        if entry.image is None:
            assert not pictures
            continue
        (pic,) = pictures
        box = Box.of(pic)
        area = image_area(slide.slide_layout, prs.slide_width, prs.slide_height)
        assert area.contains(box)
        assert (box.left, box.top) == (area.left, area.top)
        assert not box.overlaps(header)
        assert not any(box.overlaps(f) for f in footers)
        assert pic._element.nvPicPr.cNvPr.get("descr") == entry.title


def test_uses_preselected_layout_when_none_is_chosen(sample_template, sample_pages, tmp_path):
    prs = Presentation(build_deck(sample_template, _entries(sample_pages[:1]), tmp_path / "deck.pptx"))
    assert prs.slides[0].slide_layout.name == "PBI Page"


def test_error_slide_names_page_and_reason(sample_template, tmp_path):
    entry = CapturedEntry("Umsatz", URL, None, "Example", error="No report page at this address")
    slide = Presentation(build_deck(sample_template, [entry], tmp_path / "deck.pptx")).slides[0]
    text = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
    assert "Diese Seite konnte nicht erfasst werden." in text
    assert "Umsatz" in text and "No report page at this address" in text


@pytest.mark.parametrize("language, label", [("de", "Exportiert: 2026-10-19T18:43"), ("en", "Exported: 2026-10-19T18:43")])
def test_notes_trace_each_slide_back_in_the_render_language(sample_template, sample_pages, tmp_path, language, label):
    entry = CapturedEntry("Example", URL, sample_pages[0], "Example", ["financials/Country = Germany"])
    deck = build_deck(sample_template, [entry], tmp_path / "deck.pptx", language=language, exported_at=datetime(2026, 10, 19, 18, 43))
    notes = Presentation(deck).slides[0].notes_slide.notes_text_frame.text
    assert label in notes
    assert URL in notes and "financials/Country = Germany" in notes
