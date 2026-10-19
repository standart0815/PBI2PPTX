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
uv run pytest
```

`prototype/` holds the throwaway prototypes from Milestones 1 and 2. They are kept for reference and aren't part of the package.
