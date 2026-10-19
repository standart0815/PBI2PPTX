"""A sample 16:9 Template and synthetic Page Images, generated for tests.

The Template has:
- a header band on the master, ending at the bottom of the title,
- footers (date, footer text, slide number) on every page layout,
- "PBI Page": title + footers, no picture placeholder (tests the default Image Area),
- "PBI Page (Picture)": a deeper header band and a picture placeholder (tests the override),
- one existing cover slide (tests that template slides are dropped).
"""

from __future__ import annotations

import copy
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls
from pptx.util import Inches

from pbi2pptx.template import save_as_potx

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.5)
TITLE_TOP, TITLE_H = Inches(0.2), Inches(0.9)
HEADER_BOTTOM = TITLE_TOP + TITLE_H
FOOTER_TOP, FOOTER_H = Inches(6.95), Inches(0.4)


def band(left, top, width, height, rgb, shape_id):
    """A filled rectangle element, built in a scratch deck so it can be moved into a master or layout."""
    scratch = Presentation()
    slide = scratch.slides.add_slide(scratch.slide_layouts[6])
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(rgb)
    shape.line.fill.background()
    el = copy.deepcopy(shape._element)
    el.nvSpPr.cNvPr.id = shape_id
    el.nvSpPr.cNvPr.name = f"Header band {shape_id}"
    return el


def _insert_behind(shapes, element):
    shapes._spTree.insert(2, element)  # right after nvGrpSpPr and grpSpPr


def _place(ph, left, top, width, height):
    ph.left, ph.top, ph.width, ph.height = left, top, width, height


def _place_standard(placeholders):
    for ph in placeholders:
        kind = ph.placeholder_format.type
        if kind == PP_PLACEHOLDER.TITLE:
            _place(ph, MARGIN, TITLE_TOP, SLIDE_W - 2 * MARGIN, TITLE_H)
        elif kind == PP_PLACEHOLDER.DATE:
            _place(ph, MARGIN, FOOTER_TOP, Inches(2.5), FOOTER_H)
        elif kind == PP_PLACEHOLDER.FOOTER:
            _place(ph, Inches(4.17), FOOTER_TOP, Inches(5), FOOTER_H)
            ph.text_frame.text = "Vertraulich – Beispielvorlage"
        elif kind == PP_PLACEHOLDER.SLIDE_NUMBER:
            _place(ph, SLIDE_W - MARGIN - Inches(2.5), FOOTER_TOP, Inches(2.5), FOOTER_H)
        elif kind == PP_PLACEHOLDER.BODY:
            _place(ph, MARGIN, HEADER_BOTTOM + Inches(0.2), SLIDE_W - 2 * MARGIN, Inches(5.4))


def _picture_placeholder(left, top, width, height):
    return parse_xml(
        f"<p:sp {nsdecls('p', 'a')}>"
        '<p:nvSpPr><p:cNvPr id="50" name="Picture Placeholder"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        '<p:nvPr><p:ph type="pic" idx="13"/></p:nvPr></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm></p:spPr>'
        '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="de-DE"/></a:p></p:txBody>'
        "</p:sp>"
    )


def make_template(path: Path) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H

    master = prs.slide_master
    _place_standard(master.placeholders)
    _insert_behind(master.shapes, band(0, 0, SLIDE_W, HEADER_BOTTOM, "D9E2F3", 900))

    by_name = {layout.name: layout for layout in prs.slide_layouts}
    for name, layout in by_name.items():
        if name not in {"Title Slide", "Title Only", "Title and Content"}:
            prs.slide_layouts.remove(layout)

    cover = by_name["Title Slide"]
    for ph in cover.placeholders:
        if ph.placeholder_format.type == PP_PLACEHOLDER.CENTER_TITLE:
            _place(ph, MARGIN, Inches(2.4), SLIDE_W - 2 * MARGIN, Inches(1.5))
        elif ph.placeholder_format.type == PP_PLACEHOLDER.SUBTITLE:
            _place(ph, MARGIN, Inches(4.0), SLIDE_W - 2 * MARGIN, Inches(1.0))

    plain = by_name["Title Only"]
    plain._element.cSld.set("name", "PBI Page")
    _place_standard(plain.placeholders)

    picture = by_name["Title and Content"]
    picture._element.cSld.set("name", "PBI Page (Picture)")
    for ph in list(picture.placeholders):
        if ph.placeholder_format.type == PP_PLACEHOLDER.BODY:
            ph._element.getparent().remove(ph._element)
    _place_standard(picture.placeholders)
    # A sub-header strip reaching lower than the title, so the author sets the Image Area explicitly.
    _insert_behind(picture.shapes, band(0, HEADER_BOTTOM, SLIDE_W, Inches(0.45), "8EA9DB", 901))
    pic_top = HEADER_BOTTOM + Inches(0.6)
    picture.shapes._spTree.append(
        _picture_placeholder(MARGIN, pic_top, SLIDE_W - 2 * MARGIN, FOOTER_TOP - Inches(0.1) - pic_top)
    )

    slide = prs.slides.add_slide(cover)
    slide.shapes.title.text = "Beispiel-Deckblatt"
    slide.placeholders[1].text = "Diese Folie stammt aus der Vorlage"

    path.parent.mkdir(parents=True, exist_ok=True)
    save_as_potx(prs, path)
    return path


def make_page(path: Path, width: int, height: int, label: str, rgb: str) -> Path:
    """A synthetic Page Image with a grid and corner markers, so cropping or anchoring is visible."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    for x in range(0, width, 160):
        draw.line([(x, 0), (x, height)], fill="#E6E6E6", width=2)
    for y in range(0, height, 160):
        draw.line([(0, y), (width, y)], fill="#E6E6E6", width=2)
    draw.rectangle([0, 0, width - 1, height - 1], outline=f"#{rgb}", width=16)
    font = ImageFont.load_default(size=max(48, height // 14))
    draw.text((width // 2, height // 2), f"{label}\n{width}×{height}", fill=f"#{rgb}", font=font, anchor="mm", align="center")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


PAGES = [
    ("page-16x9.png", 2560, 1440, "16:9", "2F5597"),
    ("page-4x3.png", 1920, 1440, "4:3", "548235"),
    ("page-tall.png", 2560, 4800, "tall", "C55A11"),
    ("page-wide.png", 3840, 1080, "wide", "7030A0"),
]


def make_pages(folder: Path) -> list:
    return [make_page(folder / name, w, h, label, rgb) for name, w, h, label, rgb in PAGES]
