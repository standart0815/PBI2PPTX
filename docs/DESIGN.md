# PBI2PPTX: Design

A local desktop tool for Windows and macOS. Users sign in to Power BI with their own credentials in a browser window the tool controls, add the Report Pages they want, and get one Deck built from their own PowerPoint Template, with each page shown as an image. There is no Entra app registration and no Power BI API ([ADR 0003](adr/0003-local-tool-driving-power-bi-web.md)).

Terms are defined in [GLOSSARY.md](../GLOSSARY.md). The decisions behind the design are in [docs/adr/](adr/).

## Flow

1. **Start and sign-in**
   - The tool serves its interface as a local web page and opens it in the default browser.
   - It also opens the **Power BI Window**: the browser already installed on the machine (Edge on Windows, Chrome or Edge on macOS), with a persistent profile of its own.
   - The User signs in to app.powerbi.com there, on Microsoft's own sign-in page, so MFA and Conditional Access work as usual. The tool never sees the credentials.
   - The profile keeps the session between runs. **"Sign out"** deletes the profile.
2. **Building a Selection**
   - The User browses Power BI as usual in the Power BI Window: Workspaces, My workspace and Power BI Apps.
   - **"Add current page"** adds the page currently showing as an Entry. With the checkbox **"Include the filters I set"** (on by default, remembered by the interface), the Entry also takes over the page's current filters:
     - **What's taken over:** what the Filter Pane and the page's slicers show, as far as it can be written as "column = values". That includes author defaults, which is harmless because the page looks the same.
     - **What's skipped:** filters and slicers showing "Alle"/"All".
     - **What's left out:** Top N, relative date slicers and click highlights. The interface's notice lists them with the reason. Nothing about them appears on the slide.
     - **Date slicers**: the chosen from–to becomes a Date Filter with fixed dates. Only an end the User moved is taken over: an end left at the slicer's limit stays open, so that new data keeps showing in later Exports. If the slicer covers its whole available range, nothing is taken over, as with "Alle".
     - **Date cards in the Filter Pane**: a date range set in the pane, or by a page address, shows as separate cards for each end. They become one Date Filter with fixed dates:
       - "ist am oder nach X" / "is on or after X" gives from = X
       - "ist nach X" / "is after X" gives from = the day after X
       - "ist am oder vor Y" / "is on or before Y" gives to = Y
       - "ist vor Y" / "is before Y" gives to = the day before Y

       A date slicer then adds nothing of its own: Power BI narrows the slicer's available range to these cards (checked 2026-10-19).
     - **Table and column:** each Filter Pane card carries its full field name in a hidden label, such as `"financials"[Country]` (checked 2026-10-19). Slicers show only the column's display name. They take their table from a Filter Pane card with the same column. Without such a card, the slicer is left out with the note "table unknown: add this Filter by hand".
     - **Also left out, with a note:**
       - filters other than a plain "is one of": "ist nicht" (is not), contains, greater than, Top N, relative dates
       - values that look like numbers or dates: Power BI shows them formatted for the language, and a wrong guess would give silently empty visuals
       - lists the tool can't read completely: if Power BI shortens a long list, the tool opens the card and reads the ticked values. A Filter is never taken over incomplete.
     - **A visible side effect:** a slicer taken over as a Filter is applied through the page address. On the slide, the slicer itself may still show "Alle", while the data is filtered. The Filter Box shows what applies. A Page URL can also be pasted. A shared App link (`/Redirect?action=OpenApp…`) is opened in the Power BI Window and resolved to the page it lands on.
   - Each Entry holds a Page URL, a slide title (the page name by default, editable) and its Filters.
   - Filters are entered in a small form (table, column, values). The tool turns them into Power BI's URL filter syntax, for example `?filter=Table/Column in ('A','B')`. An "apply to all Entries" button covers the "same pack for each region or month" case.
   - Each Filter has an optional **"Check"** button. It opens the page with that Filter in the Power BI Window and reports whether Power BI applied it (see Filter verification).
   - Entries can be reordered by drag and drop, can repeat the same page, and can mix Reports from different Workspaces and Power BI Apps.
   - **Date Filters**: a Filter on a real date column, such as `Calendar[Date]`, can be a date range instead of "is one of these values".
     - It has a **from** and/or a **to**, both inclusive, so a single day is from = to. The end day always counts in full, even on columns that store a time: the page address says "before the next day".
     - Each end is **none**, a **fixed date**, or a **Date Rule**: Today, Yesterday, Start of this month, Start of last month, End of last month, Start of this year, Start of last year, End of last year.
     - Rules are worked out when the Export starts: "Today" is the date on the User's computer then, one date for the whole Export. A Saved Selection therefore moves along by itself from one Export to the next.
     - Year or month columns stored as numbers or text are out of scope.
     - The Filter form refuses fixed ranges where from is after to.
   - **Filter Overview**: a collapsible section below the Entry list.
     - It lists every Filter of the Selection, grouped by field ("Calendar / Date: 12 Entries"), each with a checkbox naming its Entry, plus "select all" per field.
     - Selection works within one field at a time. **Edit selected** sets the same values or date range on every selected Filter, and **Remove selected** removes them.
     - For a date range, each end also offers **"keep as is"**, preselected. "to = Today" with from = "keep as is" changes only the end and keeps each page's own start.
   - **Limits**: Power BI allows at most 10 conditions and about 2,000 characters per page address, and a Date Filter with both ends counts as two. The interface warns on an Entry over the limit.
3. **Saved Selection**
   - The Selection has a name and is saved as `<name>.json` wherever the User chooses.
   - The file holds the Page URLs, a snapshot of their names, slide titles, Filters, the Slide Layout name, the Render Language and the "Show Filters on slides" setting. It does not contain the Template.
   - Files with Date Filters use format version 2. Older PBI2PPTX versions refuse them with "comes from a newer PBI2PPTX". The new version opens every older file.
   - A colleague can open someone else's file.
4. **Export**
   - The User picks the Template (.potx), a Slide Layout (see [Slide composition](#slide-composition) for which one is preselected) and the Render Language (German by default, English possible).
   - An Export holds at most 50 Entries and runs one at a time, with a progress screen.
   - By default it runs in the **visible Power BI Window**. The User watches it step through the pages and is asked not to click in it until it's done.
   - **Hidden Export:** with "Export hidden" ticked, the pages are captured in an invisible browser instead. The browser profile can't be open twice, so the Power BI Window closes for the Export and opens again afterwards at the page it showed, also after a cancelled or failed Export. Meanwhile "Show Power BI Window" is disabled. The capture steps are the same, so the Page Images are too. If the invisible browser finds no valid sign-in, the Export stops before the first page and the Power BI Window opens for the User to sign in. The choice is remembered on the User's machine and is not part of the Saved Selection.
   - Pages are not checked when a Saved Selection is opened. A page that was deleted or can't be accessed becomes an Error Slide during the Export.
5. **Capturing**
   - For each Entry, the Power BI Window opens the Page URL with its Filters.
   - It clicks **"Reset to default"** when Power BI offers it, so persisted personal filters and slicer selections don't leak into the image. The result is the Default State plus the Entry's Filters.
   - It switches the page to **"Fit to page"**, sizes the window to the page, and captures **only the report canvas** at 2× pixel density, without Power BI's header, navigation or panes.
   - The Render Language is set through the browser's language.
   - **Filter verification:** Power BI silently ignores a URL filter whose table or column doesn't exist, which would give an unfiltered slide that looks filtered. So after opening a filtered page, the tool reads Power BI's filter pane. Every Filter Power BI accepted appears there as a card for its column showing its values (for example "Country ist Germany oder France"). The outcomes:
     - **Applied:** the card is there with every value. The page is captured.
     - **Not applied:** the card is missing or lacks a value. The Entry becomes an **Error Slide** naming the Filter ("financials/Land was not applied: check the table and column name"). The Export carries on.
     - **Not verifiable:** the report hides its filter pane. The page is captured, and the speaker notes and the Export summary say "Filter not verified".
     - **Date Filters**: each end must show as its own card with the expected date in the interface's language. "To 19.10.2026" is sent as "before 20.10.2026", so the card reads "ist vor 20.10.2026" / "is before 10/20/2026". "From" reads "ist am oder nach …" / "is on or after …". A missing card means not applied.
     - **Values that don't exist** (for example "Atlantis") are accepted by Power BI and give empty visuals. They are not detected: the slide is visibly empty, and the Export summary lists every Entry's Filters for review.
6. **Slides**: see [Slide composition](#slide-composition).
7. **Result**
   - The Deck is saved as `<name> <YYYY-MM-DD>.pptx`.
   - The Deck shows the data the exporting User is allowed to see, so row-level security can make two Users' Decks differ.

## Slide composition

- Slides that come with the .potx are **dropped**, so the Deck contains only page slides. Corporate templates usually ship example slides. Letting the User pick template slides to keep (such as a title slide or a closing slide) is a later extension. There is no automatic cover slide in v1.
- Every page slide uses the chosen Slide Layout.
  - **Preselection:** the layout with a title and the largest Image Area that no decorative graphic reaches into. If several layouts tie, the first one wins.
  - **Warning:** if the chosen layout has decorative graphics (non-placeholder shapes on the layout or master) inside its Image Area, the User sees a warning before exporting. The Image Area is not shrunk to avoid them.
  - Of the layout's placeholders, only the title and the footers are kept on the slide. Empty content, table and picture placeholders are removed.
- The Entry's slide title goes into the layout's title placeholder.
- The **Image Area** is defined as follows:
  - **Default:** the full slide width, from the bottom edge of the title placeholder (the header) down to the top of the highest footer placeholder, or to the bottom of the slide if there are no footers.
  - **Override:** if the Slide Layout has a picture placeholder, that placeholder's box is the Image Area instead. Template authors use this when the header band reaches lower than the title placeholder.
- The Page Image is made **as large as possible inside the Image Area, anchored top-left**. It is never cropped, never stretched, and never covers the header or footers.
  - It fills the full width whenever the height allows.
  - Example: a 16:9 page on a 33.9 × 19.1 cm slide whose header ends at 3 cm becomes 28.5 × 16.1 cm, with 5.3 cm left empty on the right.
- Pages with unusual sizes, such as tall scrolling pages, are fitted whole.
- **Dates on slides**: in the Render Language, e.g. "Date: 01.01.2026 – 19.10.2026" (Deutsch) or "Date: 01/01/2026 – 10/19/2026" (English). Open ends read "ab …" / "bis …" (Deutsch) or "from …" / "until …" (English). The Filter Box shows the dates; the speaker notes also name the Date Rule, e.g. "bis 19.10.2026 (Heute)".
- **Error Slides for Date Filters**: a range that turns out empty at Export (for example "from Start of this month to Yesterday" on the 1st), and a page over Power BI's limits, each get an Error Slide that says why.
- **Filter Box:** when the Deck's setting **"Show Filters on slides"** is on (off by default, stored in the Saved Selection), every slide whose Entry has Filters gets a Filter Box. Slides without Filters get none.
  - **Content:** a heading ("Filter" / "Filters", in the Render Language), then one line per Filter, such as "Country: Germany, France". The column is shown, not the table. It uses the template's font and text colour, at about 12 pt.
  - **Place:** to the right of the Page Image, 0.3 cm away, top-aligned with it. The right edge keeps the title's left margin from the slide edge, or stays inside the picture placeholder. It never covers the header or footers.
  - **Room:** the box needs at least 20 % of the Image Area's width. If the page leaves that much free on the right, it keeps its size. Otherwise the page is made just narrow enough.
- **Speaker notes** record the Report and Report Page names, a link back to the page in Power BI, the Filters applied and the Export timestamp.
- A Report Page that fails to render becomes an **Error Slide** that names the page and the reason. The Export carries on.
- Speaker-note labels and Error Slide texts follow the Render Language. The interface itself is English.

## Data handling

- Everything stays on the User's machine. Nothing is sent anywhere except to Power BI itself.
- **No update check yet.** A check of the GitHub releases page at startup is planned. It would send no report or user data, only the request any browser would make.
- The Power BI Window's profile holds a live Power BI session. It is as sensitive as a signed-in browser, and "Sign out" deletes it.
- Saved Selections and Decks are files the User keeps.
- Page Images exist only while an Export runs.

## Stack and packaging

- **Tool:** Python 3.12 (managed with `uv`), with Playwright driving the installed browser and python-pptx building the Deck.
- **Interface:** a local web page (TypeScript and React) for the Selection, drag-and-drop and the Export.
- **Packaging:** a single installer, a Windows `.exe` and a macOS `.app`, with everything included and no separate Python install. Installers are not code-signed yet.
- **Code:** a public GitHub repository under the [MIT License](../LICENSE), with CI on macOS and Windows. How the code is organised is in [ARCHITECTURE.md](ARCHITECTURE.md).
