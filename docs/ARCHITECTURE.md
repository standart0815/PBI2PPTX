# Architecture

How PBI2PPTX is built. What it does is in [DESIGN.md](DESIGN.md), and why it works this way is in [ADR 0003](adr/0003-local-tool-driving-power-bi-web.md). Terms are defined in [GLOSSARY.md](../GLOSSARY.md).

## Overview

One process per User, started by the installed app's icon.

```
┌───────────────────────── PBI2PPTX process (Python) ─────────────────────────┐
│  Local server (127.0.0.1, random port, secret token in the URL)             │
│    serves the interface, plus an API and a progress stream                  │
│        │                                                                     │
│        ├── Selection: Entries, Saved Selection JSON (versioned)             │
│        ├── Template: layouts, preselection, Decorative Graphic warnings     │
│        ├── Export: one at a time, progress, cancel, Error Slides            │
│        │      └── Deck builder                                              │
│        └── Power BI Window (async, one owner)                               │
│               installed Edge/Chrome, persistent profile                     │
└──────────────────────────────────────────────────────────────────────────────┘
   default browser: the interface         separate window: Power BI
```

- **One owner for the Power BI Window.** A single async task drives it. "Add current page" and an Export are queued, never run in parallel, and while an Export runs, "Add current page" is disabled.
- **The local server only accepts calls carrying the per-launch token.** Other websites open in the User's browser can't drive the tool.
- **Everything that depends on the Power BI interface sits in one module** ([power_bi_ui.py](../pbi2pptx/power_bi_ui.py)). That covers selectors, button texts, the tip popup and the reset dialog, so a Power BI release means one place to fix.
- **Files go through the browser.** The Template is picked with a file input. The Deck and the Saved Selection come back as downloads, so the tool needs no native file dialogs.
- **No browser is bundled.** Playwright drives the Chrome or Edge already installed on the machine; the app ships only Playwright's driver.

## Code layout

```
pbi2pptx/                  Python package
  app.py                   command line, single instance, log file, start-up
  server.py                local server, token check, API, progress stream
  window_service.py        the single owner of the Power BI Window
  power_bi_window.py       the Power BI Window: sign-in state, current page, capture
  power_bi_ui.py           selectors and texts for the Power BI interface (the brittle part)
  set_filters.py           taking over the filters a User set on a page
  page_url.py              Page URLs, App links, Filters in URL filter syntax, Power BI's limits
  dates.py                 Date Rules, dates on slides in the Render Language
  selection.py             Selection, Entry, Saved Selection JSON (schemaVersion 1; 2 with Date Filters)
  template.py              .potx handling, layouts, preselection, warnings
  deck.py                  slide composition, Image Area, Filter Box, notes, Error Slides
  export.py                runs an Export: capture → Deck, progress, cancel, 50-Entry cap
  tray.py                  menu bar / tray icon
  self_test.py             `--self-test`: offline check of a packaged app
  self_check.py            live self-check against real Power BI
ui/                        TypeScript + React (Vite), built into pbi2pptx/static/
tests/                     unit tests + a fake Power BI page for offline window tests
packaging/                 PyInstaller spec, installer scripts, third-party license collection
```

## Tests

| Level | What | When |
|---|---|---|
| Unit | Page URLs, filters, Selection JSON, Image Area, preselection, Deck | Every commit (CI) |
| Offline window | Power BI Window against the fake Power BI page ([fake_power_bi.html](../tests/fixtures/fake_power_bi.html)) | Every commit (CI) |
| Packaged app | `PBI2PPTX --self-test` builds a small Deck offline from inside the bundle | Every installer build |
| Live self-check | Real Power BI: Workspace, My workspace and Power BI App routes, Filters, Error Slide, language | Before every release, on macOS and Windows |

## Risks

- **A Power BI interface change breaks capturing.** Mitigated by keeping the brittle parts in one module, the live self-check, and releases that are quick to ship.
- **Corporate IT blocks unsigned apps or browser automation.** The installers are not code-signed yet.
- **Filter mistakes are silent in Power BI.** A wrong table or column name is ignored, and the page shows unfiltered; a value that doesn't exist empties the visuals. The tool reads Power BI's filter pane, and a Filter that wasn't applied becomes an Error Slide. Values that don't exist stay undetected, and the filter pane's layout is another part of the Power BI interface that can change.
- **Microsoft's terms on automating the Power BI website** are unclear. Organisations should check their own policies before using the tool.
