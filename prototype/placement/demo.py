"""Build sample Decks from a Template with every sample Page Image plus one Error Slide.

Usage: python demo.py [TEMPLATE.potx ...]
Without arguments it builds the sample Template first. One Deck per page Slide Layout
is written to out/.
"""

from __future__ import annotations

import sys
from pathlib import Path

from placement import Entry, build_deck, default_layout, layouts_by_name, obstructions, TITLE_TYPES
from potx import open_template
from make_samples import make_all, SAMPLES

OUT = Path(__file__).parent / "out"


def entries(pages):
    result = [
        Entry(
            title=page.stem,
            image=page,
            report="Beispielbericht",
            link="https://app.powerbi.com/groups/me/reports/…",
            filters=["Region = EMEA"] if i == 0 else [],
        )
        for i, page in enumerate(pages)
    ]
    result.append(Entry(title="Kaputte Seite", image=None, report="Beispielbericht", error="Visual-Timeout nach 60 s"))
    return result


def page_layouts(template: Path):
    """Every layout with a title, with the graphics that reach into its Image Area."""
    prs = open_template(template)
    print(f"{template.name}: preselected Slide Layout = {default_layout(prs).name}")
    result = []
    for name, layout in layouts_by_name(prs).items():
        if {ph.placeholder_format.type for ph in layout.placeholders} & TITLE_TYPES:
            try:
                result.append((name, obstructions(layout, prs.slide_width, prs.slide_height)))
            except ValueError as e:
                print(f"  skip {name}: {e}")
    return result


def main(templates):
    pages = sorted((SAMPLES / "pages").glob("*.png"))
    if not templates:
        sample, pages = make_all()
        templates = [sample]
    for template in templates:
        for layout, graphics in page_layouts(template):
            out = OUT / f"{template.stem} – {layout}.pptx"
            build_deck(template, entries(pages), out, layout_name=layout)
            warning = f"  WARNING: graphics in the Image Area: {', '.join(graphics)}" if graphics else ""
            print(f"{out}{warning}")


if __name__ == "__main__":
    main([Path(arg) for arg in sys.argv[1:]])
