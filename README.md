# PBI2PPTX

A desktop tool for Windows and macOS that turns a choice of Power BI report pages into one PowerPoint deck, built from your own PowerPoint template, with each page shown as an image.

You sign in to Power BI with your own account in a browser window the tool controls, so MFA and Conditional Access work as usual. There is no Entra app registration, no Power BI API and no admin consent, and nothing leaves your machine except the traffic to Power BI itself.

> PBI2PPTX is an independent project. It is not affiliated with, endorsed by or supported by Microsoft. Power BI, PowerPoint and Microsoft Edge are trademarks of Microsoft Corporation; Google Chrome is a trademark of Google LLC.

## What it does

- **Pick pages while you browse.** Open a report page in the Power BI Window, from a Workspace, My workspace or a Power BI App, and click **Add current page**. Page addresses and shared App links can be pasted too.
- **Filters per slide.** Restrict each page with "column is one of these values" or a date range, including Date Rules such as "Start of this year" to "Today". The filters you set on the page can be taken over. A **Filter Overview** edits the same Filter across many pages at once.
- **Filters are checked.** Power BI silently ignores a filter with a wrong table or column name. PBI2PPTX reads Power BI's filter pane and puts an Error Slide in place of a page that would otherwise look filtered but isn't.
- **Your template.** Pages go into the template's picture area as large as possible, below the title and above the footers. The tool recommends a slide layout and warns when a graphic reaches into the picture area. A Filter Box can list each slide's Filters.
- **Clean images.** Each page is reset to its default state, set to "Fit to page" and captured without Power BI's header and panes, at 2× pixel density, with numbers and dates in German or English.
- **Traceable.** Speaker notes record the report, the page, a link back to it, the Filters and the export time.
- **Saved Selections.** A list of pages with their titles and Filters is saved as a JSON file that a colleague can open too.

## Installing

Download the installer for your system from the [Releases page](https://github.com/standart0815/PBI2PPTX/releases):

- **macOS:** `PBI2PPTX-<version>-macOS.dmg`
- **Windows:** `PBI2PPTX-<version>-Windows-Setup.exe` (installs for the current user, no administrator rights needed)

You also need **Google Chrome or Microsoft Edge** installed. The installers are **not code-signed** yet, so macOS and Windows warn before the first start; [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md#installing) explains how to open them.

## Using it

[docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) is the manual: signing in, building a Selection, Filters, choosing the template and exporting the deck.

## Privacy

- PBI2PPTX runs entirely on your computer. Its interface is a local web page on `127.0.0.1`, protected by a token that changes with every start.
- It never sees your password: you sign in on Microsoft's own page. The Power BI Window keeps its own browser profile with your Power BI session; **Sign out** deletes it.
- Templates are held in memory only. Page images exist only while an export runs. The log file contains no report content.
- The deck shows what the exporting user is allowed to see, so row-level security applies as usual.

## Known limitations

- **It depends on the Power BI web interface**, which Microsoft can change without notice. A change can break capturing or filter checks until PBI2PPTX is updated ([power_bi_ui.py](pbi2pptx/power_bi_ui.py) is where such fixes go).
- **Tested mainly on macOS with Chrome.** Windows with Edge is built but not yet verified in daily use.
- **Unverified cases:** users who reach a report only through a Power BI App, resetting saved personal filters, Date Filters against real Power BI, and very long filter lists that Power BI shortens.
- **Render languages:** German and English.
- **Unsigned installers**, so some organisations' IT policies may block them.
- **Microsoft's terms** on automating the Power BI website are unclear. Check your organisation's policies before using the tool.

## Documentation

- [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md): installing and using PBI2PPTX
- [docs/DESIGN.md](docs/DESIGN.md): what the tool does, in detail
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the code is organised, tests and risks
- [docs/adr/](docs/adr/): the decisions behind the design
- [GLOSSARY.md](GLOSSARY.md): the terms used throughout
- [CHANGELOG.md](CHANGELOG.md): what changed in each version

## Development

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 itself) and [Node.js](https://nodejs.org/) 22 or newer.

```bash
uv sync
uv run playwright install chromium   # once, for the offline Power BI Window tests
uv run pytest
```

To run the tool from source, build the interface once, then start it:

```bash
npm --prefix ui install
npm --prefix ui run build
uv run pbi2pptx
```

[CONTRIBUTING.md](CONTRIBUTING.md) covers the live self-check against real Power BI, building the installers and how to propose changes.

## License

PBI2PPTX is released under the [MIT License](LICENSE). The libraries it uses and bundles keep their own licenses; see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
