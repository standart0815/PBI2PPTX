# PBI2PPTX

A local desktop tool for Windows and macOS that turns a user's choice of Power BI report pages into one PowerPoint deck, built from the user's own template, with each page shown as an image. Users sign in to Power BI with their own credentials in a browser window the tool controls. No Entra app registration or Power BI API is involved.

- [docs/DESIGN.md](docs/DESIGN.md) describes what the tool does.
- [docs/MILESTONE-3.md](docs/MILESTONE-3.md) is the build plan.
- [GLOSSARY.md](GLOSSARY.md) defines the terms.
- [docs/adr/](docs/adr/) records the decisions.

## Development

Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 itself.

```bash
uv sync
uv run playwright install chromium   # once, for the offline Power BI Window tests
uv run pytest
```

The offline tests drive a fake of the Power BI interface ([tests/fixtures/fake_power_bi.html](tests/fixtures/fake_power_bi.html)). Before every release, also run the **live self-check** against real Power BI, on macOS and on Windows:

```bash
uv run python -m pbi2pptx.self_check signin
uv run python -m pbi2pptx.self_check run --workspace <Page URL> --app <Page URL or App link> --filter "Table/Column=Value"
```

When Power BI changes its interface, the fixes go into [pbi2pptx/power_bi_ui.py](pbi2pptx/power_bi_ui.py) and the fake page.

`prototype/` holds the throwaway prototypes from Milestones 1 and 2. They are kept for reference and aren't part of the package.
