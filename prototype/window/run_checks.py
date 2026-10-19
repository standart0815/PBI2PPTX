"""Run the Milestone 2 checks (CHECKS.md) automatically, as far as they can be automated.

    ../.venv/bin/python run_checks.py signin
        Opens the Power BI Window and waits (up to 10 min) until you have signed in yourself.
    ../.venv/bin/python run_checks.py run --workspace URL --app URL --filter "Table/Column=Value"
                                          [--myworkspace URL] [--template X.potx]
        Uses the kept session; captures every page, builds Decks, and writes out/checks/RESULTS.md.

Left manual: changing a slicer by hand before the reset (check 6), Windows/Edge, and sign-out (10).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "placement"))

from PIL import Image, ImageChops  # noqa: E402

from pbi_window import Filter, PowerBIWindow, parse_page_url  # noqa: E402

OUT = HERE / "out" / "checks"
TEMPLATE = HERE.parent / "placement" / "samples" / "sample-header-footer.potx"
SIGNED_OUT_MARKERS = ("login.microsoftonline.com", "/singleSignOn", "login.live.com", "/signin")


def signed_in(window: PowerBIWindow) -> bool:
    url = window.page.url
    return url.startswith("https://app.powerbi.com/") and not any(m in url for m in SIGNED_OUT_MARKERS)


def wait_for_sign_in(window: PowerBIWindow, timeout_s: int) -> str:
    """'signed in', 'timeout' or 'window closed'."""
    window.open_power_bi()
    deadline = time.time() + timeout_s
    last = ""
    try:
        while time.time() < deadline:
            window.page.wait_for_timeout(3000)
            url = window.page.url.split("?")[0]
            if url != last:
                print("   at", url, flush=True)
                last = url
            if signed_in(window):
                window.page.wait_for_timeout(3000)  # let Power BI finish its redirects
                if signed_in(window):
                    return "signed in"
    except Exception as e:  # noqa: BLE001 - the User closed the window
        if "closed" in str(e):
            return "window closed"
        raise
    return "timeout"


def cmd_signin(args) -> None:
    with PowerBIWindow() as window:
        print(f"Power BI Window open ({window.channel}). Waiting up to {args.timeout // 60} min for you to sign in…", flush=True)
        outcome = wait_for_sign_in(window, args.timeout)
        print("CHECK 1 sign-in:", "PASS – reached " + window.page.url.split("?")[0] if outcome == "signed in" else outcome.upper(), flush=True)


class Results:
    def __init__(self):
        self.rows: List[tuple] = []

    def add(self, check: str, ok, detail: str) -> None:
        status = {True: "PASS", False: "FAIL", None: "CHECK BY EYE"}[ok]
        self.rows.append((check, status, detail))
        print(f"{status:<13} {check}: {detail}", flush=True)

    def write(self, path: Path) -> None:
        lines = ["# Milestone 2 check results", "", f"Run {datetime.now():%Y-%m-%d %H:%M}", "", "| Check | Result | Detail |", "|---|---|---|"]
        lines += [f"| {c} | {s} | {d.replace('|', '/')} |" for c, s, d in self.rows]
        path.write_text("\n".join(lines) + "\n")


def _differs(a: Path, b: Path) -> float:
    """Share of pixels that differ between two captures (0..1)."""
    with Image.open(a) as ia, Image.open(b) as ib:
        if ia.size != ib.size:
            ib = ib.resize(ia.size)
        diff = ImageChops.difference(ia.convert("RGB"), ib.convert("RGB")).convert("L").point(lambda v: 255 if v > 24 else 0)
        return sum(diff.histogram()[255:]) / (ia.size[0] * ia.size[1])


def capture_all(window: PowerBIWindow, pages, results: Results, folder: Path, language: str):
    from placement import Entry

    entries = []
    for i, (label, url, filters) in enumerate(pages, 1):
        ref = parse_page_url(url)
        out = folder / f"{i:02d} {label}.png"
        try:
            report = window.capture(ref, filters, out)
            with Image.open(out) as img:
                size = img.size
            results.add(f"capture {label} [{language}]", not report.notes,
                        f"{size[0]}×{size[1]} px, canvas `{report.canvas_selector}`, reset: {report.reset}, fit to page: {report.fit_to_page}"
                        + (f", {'; '.join(report.notes)}" if report.notes else ""))
            entries.append(Entry(label, out, ref.report, url, [str(f) for f in filters]))
        except Exception as e:  # noqa: BLE001
            entries.append(Entry(label, None, ref.report, url, [str(f) for f in filters], str(e).splitlines()[0]))
            results.add(f"capture {label} [{language}]", False if "made-up" not in label else True, str(e).splitlines()[0])
    return entries


def cmd_run(args) -> None:
    from placement import build_deck

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    folder = OUT / stamp
    folder.mkdir(parents=True, exist_ok=True)
    results = Results()
    flt = [Filter.parse(args.filter)]
    routes = [(route, url) for route, url in (("Workspace", args.workspace), ("Power BI App", args.app), ("My workspace", args.myworkspace)) if url]
    if not routes:
        sys.exit("Give at least one of --workspace, --app, --myworkspace")
    first_url = routes[0][1]
    for route, url in (("Workspace", args.workspace), ("Power BI App", args.app)):
        if not url:
            results.add(f"3 add current page ({route})", False, "NOT TESTED – no page for this route")

    with PowerBIWindow(language="de-DE") as window:
        window.open_power_bi()
        window.page.wait_for_timeout(5000)
        if not signed_in(window):
            print("Not signed in – sign in in the Power BI Window now (waiting up to 10 min)…", flush=True)
            results.add("2 session kept", False, "had to sign in again")
            outcome = wait_for_sign_in(window, 600)
            if outcome != "signed in":
                results.add("1 sign-in", False, outcome)
                results.write(folder / "RESULTS.md")
                return
        else:
            results.add("2 session kept", True, "Power BI opened without a new sign-in")

        # Check 3: "Add current page" – page name and route, for every route.
        for route, url in routes:
            window.page.goto(url)
            window._wait_until_rendered()
            try:
                ref, name = window.current_page()
                results.add(f"3 add current page ({route})", ref.via == route and name != ref.page,
                            f"name '{name}', detected route '{ref.via}', page id {ref.page}")
            except Exception as e:  # noqa: BLE001
                results.add(f"3 add current page ({route})", False, f"landed on {window.page.url[:120]} – {e}")

        # Checks 4–8: unfiltered and filtered capture per route, plus a page that doesn't exist.
        bogus = parse_page_url(first_url)
        bogus_url = bogus.url.replace(bogus.report, "00000000-0000-0000-0000-000000000000")
        pages = []
        for route, url in routes:
            pages += [(f"{route}", url, []), (f"{route} filtered", url, flt)]
        pages.append(("made-up report", bogus_url, []))
        entries = capture_all(window, pages, results, folder, "de-DE")
        deck = build_deck(Path(args.template), entries, folder / "Deck de-DE.pptx", language="de")
        results.add("4 deck built", True, str(deck.relative_to(HERE)))

        for route, _ in routes:
            a, b = folder / f"{[p[0] for p in pages].index(route) + 1:02d} {route}.png", folder / f"{[p[0] for p in pages].index(route + ' filtered') + 1:02d} {route} filtered.png"
            if a.exists() and b.exists():
                share = _differs(a, b)
                results.add(f"5 filter changes the image ({route})", share > 0.002, f"{share:.1%} of pixels differ")
        made_up = entries[-1]
        results.add("8 no access becomes an Error Slide", made_up.image is None, made_up.error or "page was captured unexpectedly")

    # Check 9: Render Language – same page in English.
    with PowerBIWindow(language="en-US") as window:
        first_route = routes[0][0]
        capture_all(window, [(first_route, first_url, [])], results, folder / "en-US", "en-US")
        de_img, en_img = folder / f"01 {first_route}.png", folder / "en-US" / f"01 {first_route}.png"
        if de_img.exists() and en_img.exists():
            results.add("9 render language changes formats", None,
                        f"compare {de_img.relative_to(HERE)} with {en_img.relative_to(HERE)} ({_differs(de_img, en_img):.1%} of pixels differ)")

    results.write(folder / "RESULTS.md")
    print("\nResults:", (folder / "RESULTS.md").relative_to(HERE))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("signin")
    s.add_argument("--timeout", type=int, default=600)
    s.set_defaults(func=cmd_signin)
    r = sub.add_parser("run")
    r.add_argument("--workspace")
    r.add_argument("--app")
    r.add_argument("--myworkspace")
    r.add_argument("--filter", required=True)
    r.add_argument("--template", default=str(TEMPLATE))
    r.set_defaults(func=cmd_run)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
