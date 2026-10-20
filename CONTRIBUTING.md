# Contributing to PBI2PPTX

Bug reports, fixes and ideas are welcome. Please open an issue first for larger changes, so we can agree on the approach before you put work in.

## Reporting a problem

Include your operating system, browser (Chrome or Edge), PBI2PPTX version and what you saw. The log file helps most; it holds no report content:

- **macOS:** `~/Library/Application Support/PBI2PPTX/pbi2pptx.log`
- **Windows:** `%LOCALAPPDATA%\PBI2PPTX\pbi2pptx.log`

Please don't attach screenshots or decks that show confidential report data.

Security problems go through [SECURITY.md](SECURITY.md), not public issues.

## Setting up

You need [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 itself) and [Node.js](https://nodejs.org/) 22 or newer.

```bash
uv sync
uv run playwright install chromium   # once, for the offline Power BI Window tests
npm --prefix ui install
npm --prefix ui run build            # again whenever ui/ changes
```

Run the tool from source:

```bash
uv run pbi2pptx                # prints the interface address; quit with Ctrl+C or from the interface
uv run pbi2pptx --tray         # also show the menu bar / tray icon, like the installed app
uv run pbi2pptx --no-open      # don't open the interface automatically
uv run pbi2pptx --port 8765    # use a fixed port instead of any free one
```

## Tests

```bash
uv run pytest                  # unit tests and the offline Power BI Window tests
npm --prefix ui run typecheck  # the interface
```

The offline tests drive a fake of the Power BI interface, [tests/fixtures/fake_power_bi.html](tests/fixtures/fake_power_bi.html). CI runs them on macOS and Windows for every pull request.

### Live self-check

Before a release, run the self-check against real Power BI on macOS and on Windows. It needs a Power BI account and report pages you can open:

```bash
uv run python -m pbi2pptx.self_check signin
uv run python -m pbi2pptx.self_check run --workspace <Page URL> --app <Page URL or App link> --filter "Table/Column=Value"
```

## When Power BI changes its interface

Everything that depends on how the Power BI web interface looks sits in [pbi2pptx/power_bi_ui.py](pbi2pptx/power_bi_ui.py). Fix it there, mirror the change in the fake page, and add or adjust an offline test.

## Building the installers

- **macOS:** `packaging/build_macos.sh` builds `dist/PBI2PPTX.app` and a `.dmg`.
- **Windows:** `packaging/build_windows.ps1` builds `dist\PBI2PPTX\` and a setup `.exe`. It needs [Inno Setup](https://jrsoftware.org/isinfo.php) 6 (`choco install innosetup`).
- **GitHub:** the *Release build* workflow builds both. Pushing a tag such as `v0.2.0` also attaches them to a draft release.

Both scripts run `PBI2PPTX --self-test` on the packaged app, which builds a small deck offline and catches files the packager left out. The build also collects the license texts of everything the app bundles ([packaging/third_party_licenses.py](packaging/third_party_licenses.py)). If you add a dependency, check that its license allows bundling, and add it to [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## Pull requests

- Keep each pull request to one change, with tests for new behaviour.
- Use the terms from [GLOSSARY.md](GLOSSARY.md) in code, interface texts and documentation.
- Update [docs/DESIGN.md](docs/DESIGN.md) and [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) when behaviour changes, and record significant design decisions as an ADR in [docs/adr/](docs/adr/).
- Add a line to [CHANGELOG.md](CHANGELOG.md) under *Unreleased*.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
