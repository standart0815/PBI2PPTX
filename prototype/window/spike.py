"""Milestone 2: the Power BI Window prototype (throwaway).

Opens Power BI in your installed browser with its own profile. You sign in and browse there;
this terminal is the stand-in for the tool's interface. Run from prototype/window:

    ../.venv/bin/python spike.py [--lang de-DE]

Commands:
    add                      add the page showing in the Power BI Window as an Entry
    add <Page URL>           add a pasted Page URL
    filter <n> T/C=A,B       add a Filter to Entry n (all: 'filter all T/C=A')
    title <n> <text>         set Entry n's slide title
    list                     show the Selection
    save <name> / load <file>   Saved Selection as JSON
    export <template.potx>   capture every Entry and build the Deck
    probe                    dump canvas candidates and buttons (to fix selectors)
    signout                  close and delete the browser profile
    quit
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import List

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "placement"))

from pbi_window import Filter, PowerBIWindow, parse_page_url, sign_out  # noqa: E402

OUT = HERE / "out"


@dataclass
class SpikeEntry:
    url: str
    title: str
    filters: List[str] = field(default_factory=list)


def _entries(selection, which: str):
    return selection if which == "all" else [selection[int(which) - 1]]


def export(window: PowerBIWindow, selection: List[SpikeEntry], template: Path, name: str, language: str) -> None:
    from placement import Entry, build_deck

    entries = []
    for i, e in enumerate(selection, 1):
        ref = parse_page_url(e.url)
        filters = [Filter.parse(f) for f in e.filters]
        image = OUT / name / f"{i:02d}.png"
        print(f"[{i}/{len(selection)}] {e.title} ({ref.via})")
        try:
            report = window.capture(ref, filters, image)
            print(f"   reset: {report.reset} | fit to page: {report.fit_to_page} | canvas: {report.canvas_selector}")
            entries.append(Entry(e.title, image, ref.report, e.url, [str(f) for f in filters]))
        except Exception as ex:  # noqa: BLE001 - becomes an Error Slide
            print("   FAILED:", str(ex).splitlines()[0])
            entries.append(Entry(e.title, None, ref.report, e.url, [str(f) for f in filters], str(ex).splitlines()[0]))
    deck = build_deck(template, entries, OUT / f"{name} {date.today().isoformat()}.pptx", language=language[:2])
    print("Deck:", deck)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="de-DE")
    args = parser.parse_args()
    selection: List[SpikeEntry] = []
    name = "Spike"

    with PowerBIWindow(language=args.lang) as window:
        window.open_power_bi()
        print(f"Power BI Window open ({window.channel}). Sign in there, then type commands. 'help' lists them.")
        while True:
            try:
                line = input("pbi2pptx> ").strip()
            except EOFError:
                break
            cmd, _, rest = line.partition(" ")
            try:
                if cmd in ("quit", "exit"):
                    break
                elif cmd == "help":
                    print(__doc__)
                elif cmd == "add":
                    if rest:
                        ref, title = parse_page_url(rest), parse_page_url(rest).page
                    else:
                        ref, title = window.current_page()
                    selection.append(SpikeEntry(ref.url, title))
                    print(f"Entry {len(selection)}: {title}  via {ref.via}  {ref.url}")
                elif cmd == "filter":
                    which, _, text = rest.partition(" ")
                    f = Filter.parse(text)
                    for e in _entries(selection, which):
                        e.filters.append(text)
                    print("Filter added:", f)
                elif cmd == "title":
                    which, _, text = rest.partition(" ")
                    _entries(selection, which)[0].title = text
                elif cmd == "list":
                    for i, e in enumerate(selection, 1):
                        print(f"{i:>2}. {e.title}  {e.filters or ''}\n    {e.url}")
                elif cmd == "save":
                    name = rest or name
                    path = OUT / f"{name}.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"name": name, "entries": [asdict(e) for e in selection]}, indent=2, ensure_ascii=False))
                    print("Saved", path)
                elif cmd == "load":
                    data = json.loads(Path(rest).read_text())
                    name, selection = data["name"], [SpikeEntry(**e) for e in data["entries"]]
                    print(f"Loaded '{name}' with {len(selection)} Entries")
                elif cmd == "export":
                    export(window, selection, Path(rest), name, args.lang)
                elif cmd == "probe":
                    print("\n".join(window.probe()))
                elif cmd == "signout":
                    break
                elif cmd:
                    print("Unknown command. 'help' lists them.")
            except Exception as ex:  # noqa: BLE001 - keep the session alive
                print("Error:", str(ex).splitlines()[0])
    if cmd == "signout":
        sign_out()
        print("Signed out: browser profile deleted.")


if __name__ == "__main__":
    main()
