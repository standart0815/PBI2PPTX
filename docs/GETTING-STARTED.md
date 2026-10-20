# Starting and using PBI2PPTX

This manual covers version 0.1.0, which is still in development. It starts, signs you in to Power BI, lets you build, save and reopen a Selection of pages, and lets you choose the Template, Slide Layout and Render Language. **Exporting the Deck comes in the next version** (Milestone 3, step 6). Until the installers exist (step 7), you start it from the project folder with a command.

Terms such as *Power BI Window*, *Selection* and *Deck* are explained in [GLOSSARY.md](../GLOSSARY.md).

## What you need

- **macOS or Windows**
- **Google Chrome or Microsoft Edge**, installed as usual. PBI2PPTX uses it for the Power BI Window. Edge is preferred on Windows and Chrome on macOS.
- **[uv](https://docs.astral.sh/uv/)**, which installs the right Python by itself.
- **[Node.js](https://nodejs.org/)** 22 or newer, only for building the interface once.

## First-time setup

In a terminal, in the project folder:

```bash
uv sync
npm --prefix ui install
npm --prefix ui run build
```

Repeat the last two commands whenever the interface (`ui/`) has changed.

## Starting

```bash
uv run pbi2pptx
```

Two windows open:

1. **The PBI2PPTX interface**, in your default browser. Everything is controlled from here.
2. **The Power BI Window**, a Chrome or Edge window with its own profile, separate from your normal browser. It opens Power BI.

The terminal shows the interface's address. It contains a secret that changes with every start, so an old bookmark won't work. Start PBI2PPTX again instead.

## Signing in

The first time, the Power BI Window shows Microsoft's sign-in page. Sign in there with your own work account, including MFA. PBI2PPTX never sees your password.

When Microsoft asks **"Stay signed in?", answer Yes.** PBI2PPTX then remembers the session, and the next start goes straight to Power BI.

## The interface

The status at the top shows what the Power BI Window is doing:

| Status | Meaning | What to do |
|---|---|---|
| Opening the Power BI Window… | The browser is starting. | Wait a few seconds. |
| Sign in to Power BI in the Power BI Window | Power BI wants you to sign in. | Sign in there. |
| **Signed in to Power BI** | Ready. | Browse to your pages in the Power BI Window. |
| The Power BI Window is closed | You closed it. | Click **Reopen Power BI Window**. |
| The Power BI Window could not open | Neither Chrome nor Edge could be started. | Install one of them, then click **Reopen Power BI Window**. |

The buttons:

- **Show Power BI Window** brings the window to the front, and reopens it if it was closed.
- **Sign out** deletes the Power BI Window's profile, and with it your Power BI session. You'll sign in again on the next start. Use this on shared computers.
- **Quit PBI2PPTX** closes the Power BI Window and stops the tool. Pressing **Ctrl+C** in the terminal does the same.

## Building a Selection

A Selection is the ordered list of pages that will become your Deck, one slide per Entry. You can add at most 50 Entries.

### Adding pages

- **Add current page:** open a report page in the Power BI Window, from a Workspace, My workspace or a Power BI App, then click **Add current page**. PBI2PPTX takes the page that is showing.
- **Paste address:** click **Paste address** and paste either a page's address from the browser's address bar, or a **shared App link** (`…/Redirect?action=OpenApp…`). PBI2PPTX opens it in the Power BI Window and adds the page it lands on.

Each Entry shows its page, its report, and how you reach it (Workspace, My workspace or Power BI App).

### Editing Entries

- **Slide title:** click the title and type. It starts as the page's name. If you leave it empty, the page name comes back.
- **Order:** drag an Entry by its handle (⋮⋮), or use **↑** and **↓**.
- **Duplicate:** puts a copy right below, so you can include the same page twice, for example with different Filters.
- **Remove:** takes the Entry out.

### Filters

Click **Filters** on an Entry to restrict what the page shows on its slide, for example only Germany:

| Field | Example | Where to find it |
|---|---|---|
| Table | `financials` | The table's name in the report's data |
| Column | `Country` | The column's name in that table |
| Values | `Germany, France` | One or more values, separated by commas |

**Add Filter** adds it. **Apply to all Entries** copies it to every Entry, for example to build the same pack for one region. Without Filters, a page is captured as published.

Power BI doesn't report Filter mistakes, so check the slides:
- **A table or column name that doesn't match** is silently ignored, and the slide shows the page **unfiltered**. Names must match the report's data model exactly.
- **A value that doesn't exist** empties the visuals, and the slide shows **empty tables and charts**.
- **A value made only of digits**, such as `2026`, is treated as a number. On a text column, that Filter won't match.

### Saving and opening

- **Save** downloads the Selection as `<name>.json` into your downloads folder. The name comes from the field at the top, without characters that file names can't hold.
- **Open…** loads a saved file. It replaces the current Selection, after asking.
- **New** starts an empty Selection, after asking.

A Saved Selection holds the page addresses, titles and Filters, but no report data. A colleague can open your file; pages they can't access will fail at export.

The Selection also survives a reload of the interface tab. **Quit** and closing the tab don't keep it, so save first.

## Template & settings

### Choosing the Template

Click **Choose template…** and pick your company's PowerPoint template (`.potx`). A presentation (`.pptx`) also works. The panel then shows the file name and the slide size.

- **The template's own slides are left out.** Example slides such as a title slide or "Thank you" don't go into the Deck, only your pages do. The panel says how many there are.
- **The Template isn't stored anywhere.** PBI2PPTX keeps it in memory while it runs, so after a restart you choose it again. A Saved Selection remembers the Slide Layout's name, but not the file.

### Choosing the Slide Layout

Every page slide uses the same layout from the Template. PBI2PPTX recommends one: the layout with the largest picture area that no graphic reaches into. You can choose any other.

- **⚠ "A graphic reaches into the picture area"** means the layout has a picture or shape, such as an illustration, where your pages would go. Pages may collide with it. The sketch shows it in red.
- **The sketch** shows the chosen layout: title and footers in grey, the picture area dashed. Pages go into the picture area as large as possible, anchored top left, and never cover the title or footers.
- If a Saved Selection asks for a layout this Template doesn't have, PBI2PPTX uses the recommended one and says so.

### Render Language

Chooses how numbers and dates appear in the pages: **Deutsch** (`1.234,56`, `31.12.2026`) or **English** (`1,234.56`, `12/31/2026`). Texts stored in the report data, such as month names in a column, stay as they are.

## Options

```bash
uv run pbi2pptx --no-open      # don't open the interface automatically; open the printed address yourself
uv run pbi2pptx --port 8765    # use a fixed port instead of any free one
uv run pbi2pptx --version
```

## What is stored, and where

Only the Power BI Window's profile, which includes your Power BI session:

- **macOS:** `~/Library/Application Support/PBI2PPTX/profile`
- **Windows:** `%LOCALAPPDATA%\PBI2PPTX\profile`

**Sign out** deletes it. Nothing is sent anywhere except to Power BI.

## Troubleshooting

| You see | Cause | Fix |
|---|---|---|
| "The interface isn't built yet" | The interface build is missing. | Run `npm --prefix ui install` and `npm --prefix ui run build`, then reload. |
| "Please start PBI2PPTX from its icon or command" | An address from an earlier start. | Start PBI2PPTX again and use the new address. |
| "PBI2PPTX isn't running" | The tool was quit, or the terminal was closed. | Start it again. |
| The start takes up to 30 seconds | The Power BI Window from the last run is still closing. | Wait. PBI2PPTX waits for it. |
| Power BI asks you to sign in every time | You answered "No" to "Stay signed in?", or your company doesn't allow it. | Answer Yes. If your company forbids it, you'll sign in on every start. |
