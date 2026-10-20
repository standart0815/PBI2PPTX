"""Live self-check against real Power BI. Run before every release, on macOS and on Windows.

    uv run python -m pbi2pptx.self_check signin
        Opens the Power BI Window and waits (up to 10 min) until you have signed in yourself.

    uv run python -m pbi2pptx.self_check run --workspace URL --app URL [--myworkspace URL]
                                             --filter "Table/Column=Value" [--template X.potx]
        Uses the kept session. For each route: reads the current page, captures it with and
        without the Filter, then a page that doesn't exist, then once more in English, then once
        more in a hidden browser (Hidden Export).
        Writes Page Images, an optional Deck and RESULTS.md to out/self-check/<timestamp>/.

--app also accepts a shared App link (/Redirect?action=OpenApp…). Use pages whose Filter
visibly changes the numbers. Look at the images afterwards: some checks need your eyes.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops

from .deck import CapturedEntry, build_deck
from .page_url import Filter, PageUrl
from .power_bi_window import NotAReportPage, PowerBIWindow, SignIn


class Results:
    def __init__(self):
        self.rows: list = []

    def add(self, check: str, ok: bool | None, detail: str) -> None:
        status = {True: "PASS", False: "FAIL", None: "CHECK BY EYE"}[ok]
        self.rows.append((check, status, detail))
        print(f"{status:<13} {check}: {detail}", flush=True)

    def write(self, path: Path) -> None:
        lines = [
            "# Self-check results",
            "",
            f"Run {datetime.now():%Y-%m-%d %H:%M}",
            "",
            "| Check | Result | Detail |",
            "|---|---|---|",
        ]
        lines += [f"| {c} | {s} | {d.replace('|', '/')} |" for c, s, d in self.rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @property
    def failed(self) -> bool:
        return any(status == "FAIL" for _, status, _ in self.rows)


def share_of_changed_pixels(a: Path, b: Path) -> float:
    with Image.open(a) as ia, Image.open(b) as ib:
        ib = ib.resize(ia.size) if ia.size != ib.size else ib
        diff = ImageChops.difference(ia.convert("RGB"), ib.convert("RGB")).convert("L").point(lambda v: 255 if v > 24 else 0)
        return diff.histogram()[255] / (ia.size[0] * ia.size[1])


async def signin(timeout_s: int) -> SignIn:
    async with PowerBIWindow() as window:
        print(f"Power BI Window open ({window.browser}). Sign in there; waiting up to {timeout_s // 60} min…", flush=True)
        outcome = await window.wait_for_sign_in(timeout_s)
        print("Sign-in:", outcome.value, flush=True)
        return outcome


async def run(routes: list, flt: Filter, template: Path | None, folder: Path) -> Results:
    results = Results()
    entries: list = []
    first: PageUrl | None = None

    async with PowerBIWindow(language="de-DE") as window:
        await window.open_home()
        await window.page.wait_for_timeout(5000)
        if window.is_signed_in():
            results.add("session kept", True, "Power BI opened without a new sign-in")
        else:
            results.add("session kept", False, "not signed in – sign in in the Power BI Window (waiting up to 10 min)")
            if await window.wait_for_sign_in(600) is not SignIn.SIGNED_IN:
                return results

        for route, address in routes:
            try:
                current = await window.resolve(address)
            except (NotAReportPage, ValueError) as e:
                results.add(f"current page ({route})", False, str(e))
                continue
            page_url = current.page_url
            first = first or page_url
            results.add(
                f"current page ({route})",
                page_url.reached_through.value == route and current.page_name != page_url.page,
                f"'{current.page_name}' in '{current.report_name}', reached through {page_url.reached_through.value}",
            )
            images = {}
            for label, filters in ((route, []), (f"{route} filtered", [flt])):
                out = folder / f"{len(entries) + 1:02d} {label}.png"
                try:
                    report = await window.capture(page_url, filters, out)
                    with Image.open(out) as img:
                        size = img.size
                    results.add(
                        f"capture {label}",
                        not report.notes,
                        f"{size[0]}×{size[1]} px in {report.seconds} s, reset: {report.reset}, fit to page: {report.fit_to_page}, filters: {report.filters.value}"
                        + (f", {'; '.join(report.notes)}" if report.notes else ""),
                    )
                    images[label] = out
                    entries.append(CapturedEntry(label, page_url.url, out, current.report_name, [str(f) for f in filters]))
                except Exception as e:  # noqa: BLE001 - every failure is a result, not a crash
                    results.add(f"capture {label}", False, str(e).splitlines()[0])
                    entries.append(CapturedEntry(label, page_url.url, None, current.report_name, error=str(e).splitlines()[0]))
            if len(images) == 2:
                share = share_of_changed_pixels(*images.values())
                results.add(f"filter changes the image ({route})", share > 0.002, f"{share:.1%} of pixels differ")

        if first:
            missing = PageUrl(first.workspace, first.app, "00000000-0000-0000-0000-000000000000", first.page, first.ctid)
            try:
                await window.capture(missing, [], folder / "missing.png")
                results.add("missing page fails cleanly", False, "a page was captured unexpectedly")
            except NotAReportPage as e:
                results.add("missing page fails cleanly", True, str(e))
                entries.append(CapturedEntry("missing page", missing.url, None, error=str(e)))

    if first:
        async with PowerBIWindow(language="en-US") as window:
            out = folder / "en-US.png"
            await window.capture(first, [], out)
            de = next(iter(e.image for e in entries if e.image), None)
            if de:
                results.add(
                    "render language",
                    None,
                    f"compare {de.name} with {out.name}: number formats should differ ({share_of_changed_pixels(de, out):.1%} of pixels differ)",
                )

        async with PowerBIWindow(language="de-DE", headless=True) as window:
            await window.open_home()
            await window.page.wait_for_timeout(5000)
            if not window.is_signed_in():
                results.add("hidden session kept", False, f"the hidden browser isn't signed in – it shows {window.page.url.split('?')[0]}")
            else:
                results.add("hidden session kept", True, "Power BI opened signed in without a window")
                out = folder / "hidden.png"
                try:
                    await window.capture(first, [], out)
                    visible = next(iter(e.image for e in entries if e.image), None)
                    with Image.open(out) as hidden_img, Image.open(visible) as visible_img:
                        same_size = hidden_img.size == visible_img.size
                        detail = f"{hidden_img.size[0]}×{hidden_img.size[1]} px, visible {visible_img.size[0]}×{visible_img.size[1]} px"
                    results.add("hidden capture matches", same_size, f"{detail}, {share_of_changed_pixels(visible, out):.1%} of pixels differ")
                except Exception as e:  # noqa: BLE001 - every failure is a result, not a crash
                    results.add("hidden capture matches", False, str(e).splitlines()[0])

    if template and entries:
        deck = build_deck(template, entries, folder / "Deck.pptx")
        results.add("deck built", True, deck.name)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pbi2pptx.self_check", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("signin")
    s.add_argument("--timeout", type=int, default=600)
    r = sub.add_parser("run")
    r.add_argument("--workspace")
    r.add_argument("--app")
    r.add_argument("--myworkspace")
    r.add_argument("--filter", required=True)
    r.add_argument("--template", type=Path)
    r.add_argument("--out", type=Path, default=Path("out") / "self-check")
    args = parser.parse_args(argv)

    if args.cmd == "signin":
        return 0 if asyncio.run(signin(args.timeout)) is SignIn.SIGNED_IN else 1

    routes = [(name, url) for name, url in (("Workspace", args.workspace), ("Power BI App", args.app), ("My workspace", args.myworkspace)) if url]
    if not routes:
        parser.error("give at least one of --workspace, --app, --myworkspace")
    folder = args.out / datetime.now().strftime("%Y%m%d-%H%M")
    folder.mkdir(parents=True, exist_ok=True)
    results = asyncio.run(run(routes, Filter.parse(args.filter), args.template, folder))
    results.write(folder / "RESULTS.md")
    print(f"\nResults: {folder / 'RESULTS.md'}")
    return 1 if results.failed else 0


if __name__ == "__main__":
    sys.exit(main())
