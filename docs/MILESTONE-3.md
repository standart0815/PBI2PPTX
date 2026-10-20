# Milestone 3: the real tool

Turns the two prototypes into the tool described in [DESIGN.md](DESIGN.md): a local desktop tool for Windows and macOS, with a local web interface and the Power BI Window ([ADR 0003](adr/0003-local-tool-driving-power-bi-web.md)). Terms are defined in [GLOSSARY.md](../GLOSSARY.md).

**Accepted risks**, from [CHECKS.md](../prototype/window/CHECKS.md): App-only Users, resetting saved personal filters, and Windows with Edge are unproven. The pilot (step 8) covers them.

## Decisions (2026-10-19)

- **Code:** a Git repository hosted as a **private GitHub repository**. CI builds and tests on macOS and Windows.
- **Signing:** installers are **unsigned for the internal pilot**, and pilot users get instructions for opening them. They are **signed before the tool goes to other organisations**: an Apple Developer membership for macOS and a code-signing certificate for Windows.
- **Updates:** at startup the tool checks the GitHub releases page and shows "new version available". The check sends no report or user data.
- **Python:** 3.12, managed with `uv`.

## Architecture

One process per User, started by the installer's app icon.

```
┌───────────────────────── PBI2PPTX process (Python) ─────────────────────────┐
│  Local server (127.0.0.1, random port, secret token in the URL)             │
│    serves the interface, plus an API and a progress stream                  │
│        │                                                                     │
│        ├── Selection: Entries, Saved Selection JSON (versioned)             │
│        ├── Template: layouts, preselection, Decorative Graphic warnings     │
│        ├── Export: one at a time, progress, cancel, Error Slides            │
│        │      └── Deck builder (from prototype/placement)                   │
│        └── Power BI Window (from prototype/window, async)                   │
│               installed Edge/Chrome, persistent profile                     │
└──────────────────────────────────────────────────────────────────────────────┘
   default browser: the interface         separate window: Power BI
```

- **One owner for the Power BI Window.** A single async task drives it. "Add current page" and an Export are queued, never run in parallel, and while an Export runs, "Add current page" is disabled.
- **The local server only accepts calls carrying the per-launch token.** Other websites open in the User's browser can't drive the tool.
- **Everything that depends on the Power BI interface sits in one module.** That covers selectors, button texts, the tip popup and the reset dialog, so a Power BI release means one place to fix.
- **Files go through the browser.** The Template is picked with a file input. The Deck and the Saved Selection come back as downloads, so the tool needs no native file dialogs.

## Code layout

```
pbi2pptx/                  Python package
  server.py                local server, token check, progress stream
  selection.py             Selection, Entry, Filter, Saved Selection JSON (schemaVersion 1)
  page_url.py              Page URL parsing, App redirect links, URL filter syntax
  power_bi_window.py       the Power BI Window: sign-in state, current page, capture
  power_bi_ui.py           selectors and texts for the Power BI interface (the brittle part)
  template.py              .potx handling, layouts, preselection, warnings
  deck.py                  slide composition, Image Area, notes, Error Slides
  export.py                runs an Export: capture → Deck, progress, cancel, 50-Entry cap
ui/                        TypeScript + React (Vite), built into the package
tests/                     unit tests + a fake Power BI page for offline window tests
packaging/                 PyInstaller specs, installer scripts
```

## Steps

Each step ends with something runnable and tested.

1. **Foundation.**
   - Git repository, `pyproject.toml` with uv on Python 3.12, CI running the tests on macOS and Windows.
   - Port the prototype logic with its tests: `page_url`, `deck`, `template`.
   - Done when: the CI is green on both systems.
2. **Power BI Window, made robust.**
   - Port `pbi_window.py` to the async API, with everything brittle moved into `power_bi_ui.py`.
   - Add a **fake Power BI page**: a local HTML fixture that mimics the canvas, pages pane, App navigation, tip popup and reset dialog. The automation can then be tested offline and in CI.
   - Add a **live self-check** (today's `run_checks.py`) to run against real Power BI before every release.
   - Done when: the offline tests pass in CI and the live self-check passes locally.
   - Status (2026-10-19): **done locally.** It has `power_bi_window.py`, `power_bi_ui.py`, the fake page with 11 offline tests, and `python -m pbi2pptx.self_check`. The live self-check passes on macOS with Chrome across all three routes, taking about 10 s per page. CI runs once the repository is pushed.
3. **Local server and interface shell.**
   - Server with token check, the React app, and a status bar showing whether the User is signed in, plus "Sign out".
   - Done when: launching opens the interface and the Power BI Window, and the sign-in state shows correctly.
   - Status (2026-10-19): **done locally.** `uv run pbi2pptx` starts the server, the interface and the Power BI Window. The interface has sign-in status, Show, Sign out and Quit. Start manual: [GETTING-STARTED.md](GETTING-STARTED.md). The update check (decision Q54) waits for the GitHub repository URL.
4. **Building a Selection.**
   - "Add current page", pasting a Page URL or an App link, the Entry list with drag-and-drop, slide titles, delete.
   - The Filter form (table, column, values) with "apply to all Entries".
   - Saving and opening a Saved Selection.
   - Done when: a Selection can be built, saved, reopened and edited.
   - Status (2026-10-19): **done locally.** `selection.py` holds the Saved Selection format (schemaVersion 1). The API offers adding the current page, pasting addresses (including App links), and saving and opening. The interface has an Entry list with titles, drag-and-drop or ↑/↓, Duplicate and Remove, plus Filters with "Apply to all Entries". Tried live with Workspace and App pages; 68 tests in total.
5. **Template and settings.**
   - Pick the .potx, then list its layouts with the preselection and warnings, and choose the Render Language.
   - Done when: Firmenvorlage preselects "Tabelle" and shows the warnings found in Milestone 1.
   - Status (2026-10-19): **done locally.** A Template is uploaded into memory only and described with layout geometry. The interface shows the layout list with the recommendation and warnings, a sketch of the chosen layout, and the Render Language. A Saved Selection's missing layout falls back to the recommendation. Checked with Firmenvorlage: "Tabelle" is preselected, and the same five layouts are warned as in Milestone 1. 73 tests in total. The file picker itself was not operated in the check: the upload went through the same API.
6. **Export.**
   - Progress per Entry, cancel, Error Slides, Deck download named `<name> <YYYY-MM-DD>.pptx`.
   - **Filter verification** from Power BI's filter pane (decisions Q56–Q59, recorded in DESIGN.md under Capturing): a Filter that wasn't applied gives an Error Slide, and a hidden filter pane gives "Filter not verified". Plus the optional "Check" button per Filter in the interface. The fake Power BI page gets a filter pane to test it offline.
   - Done when: a Selection of 20 Entries across all three routes exports into Firmenvorlage.
   - Status (2026-10-19): **done locally.** `export.py` runs the Export in the background, switches the Power BI Window to the Render Language, verifies Filters in Power BI's filter pane, and turns failures into Error Slides with reasons in the Render Language. The API covers starting, progress, cancelling and downloading, plus the "Check" endpoint. The interface has the Export panel and a "Check" button per Filter. 84 tests in total. Live: 20 Entries across Workspace, Power BI App and My workspace exported into Firmenvorlage in about 3.6 minutes (8–14 s per page): 18 captured, plus 2 Error Slides as intended for a typo Filter and a deleted report. The "Check" button found the typo live too.
7. **Packaging.**
   - PyInstaller builds for macOS (`.app` in a `.dmg`) and Windows (`.exe` installer), built in CI.
   - First-run experience: browser check, then sign-in.
   - Done when: a clean machine without Python installs and runs it.
8. **Pilot.**
   - You and 2–3 colleagues, at least one on Windows with Edge, and one who reaches a report **only through a Power BI App**.
   - This closes the accepted risks. Collect problems with the Power BI interface and fix them in `power_bi_ui.py`.
   - Done when: the pilot users export their real decks without help.

## Test strategy

| Level | What | When |
|---|---|---|
| Unit | Page URLs, filters, Selection JSON, Image Area, preselection | Every commit (CI) |
| Offline window | Power BI Window against the fake Power BI page | Every commit (CI) |
| Live self-check | Real Power BI: three routes, Filters, Error Slide, language | Before every release, on macOS and Windows |
| Pilot | Real users, real reports, real templates | Step 8 |

## Risks

- **A Power BI interface change breaks capturing.** Mitigated by keeping the brittle parts in one module, the live self-check, and releases that are quick to ship.
- **Corporate IT blocks unsigned apps or browser automation.** The pilot stays internal and unsigned. Signing is required before other organisations get the tool.
- **Filter mistakes are silent in Power BI.** Tested 2026-10-19: a wrong table or column name is ignored, and the page shows unfiltered; a value that doesn't exist empties the visuals. **Decided (Q56–Q59):** the tool reads Power BI's filter pane, and a Filter that wasn't applied becomes an Error Slide. Values that don't exist stay undetected. Remaining risk: the filter pane's layout is another part of the Power BI interface that can change.
- **Microsoft's terms on automating the Power BI website.** These are unclear (research found nothing specific). Worth a look before giving the tool to other organisations.
