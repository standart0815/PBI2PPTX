# Starting and using PBI2PPTX

This manual covers version 0.1.0. It covers the whole path: install, sign in to Power BI, build a Selection of pages, choose the Template, Slide Layout and Render Language, and export the Deck.

Terms such as *Power BI Window*, *Selection* and *Deck* are explained in [GLOSSARY.md](../GLOSSARY.md).

## What you need

- **macOS or Windows**
- **Google Chrome or Microsoft Edge**, installed as usual. PBI2PPTX uses it for the Power BI Window. Edge is preferred on Windows and Chrome on macOS.

## Installing

Download the installer for your system from the [Releases page](https://github.com/standart0815/PBI2PPTX/releases). The installers are **not code-signed** yet, so macOS and Windows warn before the first start. This is expected.

**macOS:** open `PBI2PPTX-0.1.0-macOS.dmg` and drag **PBI2PPTX** into **Applications**. On the first start, macOS says it can't check the app:
1. Click **Done**.
2. Open **System Settings → Privacy & Security**, scroll down to "PBI2PPTX was blocked…", and click **Open Anyway**.

From then on it starts normally.

**Windows:** run `PBI2PPTX-0.1.0-Windows-Setup.exe`. If SmartScreen says "Windows protected your PC", click **More info → Run anyway**. The installer needs no administrator rights. It installs for you only and adds PBI2PPTX to the Start menu, optionally to the desktop too. Uninstall it under *Settings → Apps*.

## Starting

Start **PBI2PPTX** from *Applications* (macOS) or the Start menu (Windows). Three things appear:

1. **The PBI2PPTX interface**, in your default browser. Everything is controlled from here.
2. **The Power BI Window**, a Chrome or Edge window with its own profile, separate from your normal browser. It opens Power BI.
3. **The PBI2PPTX icon** (a blue tile with three white bars) in the **menu bar** (macOS) or the **notification area** next to the clock (Windows). PBI2PPTX has no window of its own. This icon shows that it's running:
   - **Open PBI2PPTX** brings the interface back, for example after you closed its tab.
   - **Quit PBI2PPTX** stops it and closes the Power BI Window.

Starting PBI2PPTX while it is already running opens its interface again instead of starting a second copy (on macOS, use the menu bar icon).

The interface's address contains a secret that changes with every start, so a bookmark won't work. Use the icon instead.

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
- **Quit PBI2PPTX** closes the Power BI Window and stops the tool, like **Quit** in the menu bar / tray icon.

## Building a Selection

A Selection is the ordered list of pages that will become your Deck, one slide per Entry. You can add at most 50 Entries.

### Adding pages

- **Add current page:** open a report page in the Power BI Window, from a Workspace, My workspace or a Power BI App, then click **Add current page**. PBI2PPTX takes the page that is showing.
  - With **Include the filters I set** ticked (the default, and remembered), the Entry also takes over what you set on the page: filters in Power BI's **Filter Pane** and selections in its **slicers**, such as "Discount Band: Low, Medium". They become ordinary Filters that you can edit or check.
  - Taken over are "column is one of these text values", and **date ranges**: a date slider's chosen from–to, and date conditions in the Filter Pane such as "ist am oder nach 01.06.2013". All date settings on one column become one Date Filter with fixed dates. A date slider over its whole range isn't a filter, and an end left at the slider's limit stays open, so new data keeps showing.
  - Everything else is listed under **Not taken over**, with the reason: number ranges, "is not", contains, greater than, Top N, relative dates, number or date values, dates PBI2PPTX can't read, and slicers whose table PBI2PPTX can't find. Add those by hand in the Filter form if you need them.
  - Whatever shows "Alle"/"All" isn't a filter and is skipped.
  - On the slide, a slicer may still show its full list even though the data is filtered. Turn on **Show Filters on slides** to make clear what applies.
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

For a real date column, such as `Calendar` / `Date`, choose **Date range** instead of Values. **From** and **To** both count in full, so a single day is from = to. Each end is:
- **None (open)**: no limit on that side.
- **Fixed date**: picked in the calendar.
- **A Date Rule**: Today, Yesterday, Start of this month, Start of last month, End of last month, Start of this year, Start of last year or End of last year. Rules are worked out when the Export starts, from your computer's date, so a saved Selection "from Start of this year to Today" moves along by itself from one Export to the next.

A fixed range whose from is after its to is refused. Year or month columns stored as numbers or text ("2026", "Oktober") can't take a date range.

**Add Filter** adds it. **Apply to all Entries** copies it to every Entry, for example to build the same pack for one region. Without Filters, a page is captured as published.

**Check** opens the page with that Filter in the Power BI Window and tells you, in about 10 seconds, whether Power BI applied it:
- **✓ Power BI applied it.**
- **✗ Power BI didn't recognise …**: the table or column name doesn't match the report's data model. Fix the names.
- **? Can't check**: the report hides its filter pane.

Checking is optional, because the Export checks every Filter anyway. It's a quick way to catch typos while you build the Selection.

Mistakes Power BI itself doesn't report:
- **A table or column name that doesn't match** is silently ignored by Power BI. PBI2PPTX catches it: "Check" shows ✗, and the Export puts an Error Slide in its place instead of an unfiltered page.
- **A value that doesn't exist** empties the visuals, and the slide shows **empty tables and charts**.
- **A value made only of digits**, such as `2026`, is treated as a number. On a text column, that Filter won't match.

Power BI accepts at most **10 filter conditions** per page, and a page address of about **2,000 characters**. A Date Filter with from and to counts as two. An Entry over either limit shows a warning, and the Export gives it an Error Slide.

### Filter Overview

Below the Entries, **Filter Overview** lists every Filter of the Selection, grouped by column, such as "Calendar / Date · 12 Entries". Open it to change many Filters at once, for example to move every date range up to today:

1. Tick the Filters you want, or the column's box for all of them. You can only tick within one column at a time.
2. **Edit selected** sets the same values or date range on all of them. For a date range, each end starts at **Keep as is**: set **To** to **Today** and leave **From** as it is, and every page keeps its own start.
3. **Remove selected** takes them out of their Entries, after asking.

If the change would leave any page with a from after its to, nothing is changed and the overview names the Entries.

### Saving and opening

- **Save** downloads the Selection as `<name>.json` into your downloads folder. The name comes from the field at the top, without characters that file names can't hold.
- **Open…** loads a saved file. It replaces the current Selection, after asking.
- **New** starts an empty Selection, after asking.

A Saved Selection holds the page addresses, titles and Filters, but no report data. A colleague can open your file; pages they can't access will fail at export. A file with Date Filters needs this version of PBI2PPTX or newer; older versions say it "comes from a newer PBI2PPTX".

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

### Filters on slides

**Show Filters on slides** adds a **Filter Box** to every slide whose Entry has Filters. It lists them under the heading "Filter" ("Filters" in English), one line each, such as "Country: Germany, France". Date Filters show the dates used, in the Render Language: "Date: 01.01.2026 – 19.10.2026", "Date: ab 01.01.2026" or "Date: bis 19.10.2026" ("from …", "until …" in English). The speaker notes also name the Date Rule, such as "19.10.2026 (Heute)". The box sits to the right of the page, top-aligned, in the template's font and colour.

- If the page leaves enough room on the right (at least a fifth of the picture area), the page keeps its size.
- Otherwise the page is made just narrow enough.
- Slides without Filters look as before.

The setting is stored in the Saved Selection, and it's off by default.

### Render Language

Chooses how numbers and dates appear in the pages: **Deutsch** (`1.234,56`, `31.12.2026`) or **English** (`1,234.56`, `12/31/2026`). Texts stored in the report data, such as month names in a column, stay as they are.

## Exporting the Deck

The **Export** panel says what's missing before you can start: pages, a Template, or the sign-in. When everything is there, click **Export Deck**.

- **The Power BI Window works through every page**, about 10 seconds each, so 20 pages take 3–4 minutes. Please don't click in it meanwhile. "Show Power BI Window" still works if you want to watch.
- **If you chose English as the Render Language**, the Power BI Window first restarts in English. Your sign-in is kept.
- **Progress** shows which page is being captured. **Cancel after this page** stops the Export, and then no Deck is made.
- Adding pages, pasting addresses and checking Filters wait until the Export has finished.

When it's done, the panel shows a summary and each Entry's result:

| Mark | Meaning | On the slide |
|---|---|---|
| ✓ | Captured, and every Filter was applied | The page |
| ? | Captured, but its Filters couldn't be verified because the report hides its filter pane | The page; the speaker notes say "Filter-Prüfung: nicht möglich" |
| ✗ | Not captured: page deleted, no access, a Filter Power BI didn't apply, a date range that is empty on the day of the Export (such as "Start of this month to Yesterday" on the 1st), or more Filters than Power BI accepts | An **Error Slide** naming the page and the reason |

**Download Deck** saves `<Selection name> <date>.pptx` into your downloads folder. The Deck stays available until you export again or quit PBI2PPTX, at most one hour. The Page Images are deleted as soon as the Export ends.

Each slide's **speaker notes** say where it came from: the report, the page, its address in Power BI, the Filters and the export time. That lets anyone trace a slide back later.

## For developers

Running PBI2PPTX from the project folder, the tests and building the installers are covered in [CONTRIBUTING.md](../CONTRIBUTING.md).

## What is stored, and where

In one folder:

- **macOS:** `~/Library/Application Support/PBI2PPTX/`
- **Windows:** `%LOCALAPPDATA%\PBI2PPTX\`

It holds:
- `profile/`: the Power BI Window's profile, which includes your Power BI session. **Sign out** deletes it.
- `pbi2pptx.log`: what PBI2PPTX did (starts, quits, errors). Never report content. Send it along when reporting a problem.
- `instance.json`: while PBI2PPTX runs, so a second start can find it.

Nothing is sent anywhere except to Power BI.

## Troubleshooting

| You see | Cause | Fix |
|---|---|---|
| You closed the interface tab | PBI2PPTX is still running. | Menu bar / tray icon → **Open PBI2PPTX**. |
| "Please start PBI2PPTX from its icon or command" | An address from an earlier start. | Use the icon's **Open PBI2PPTX**, or start PBI2PPTX. |
| "PBI2PPTX isn't running" | PBI2PPTX was quit. | Start it again. |
| "The interface isn't built yet" | Developer start without the interface build. | Run `npm --prefix ui install` and `npm --prefix ui run build`, then reload. |
| The start takes up to 30 seconds | The Power BI Window from the last run is still closing. | Wait. PBI2PPTX waits for it. |
| Power BI asks you to sign in every time | You answered "No" to "Stay signed in?", or your company doesn't allow it. | Answer Yes. If your company forbids it, you'll sign in on every start. |
