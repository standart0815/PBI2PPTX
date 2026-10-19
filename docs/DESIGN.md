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
   - **"Add current page"** adds the page currently showing as an Entry. A Page URL can also be pasted. A shared App link (`/Redirect?action=OpenApp…`) is opened in the Power BI Window and resolved to the page it lands on.
   - Each Entry holds a Page URL, a slide title (the page name by default, editable) and its Filters.
   - Filters are entered in a small form (table, column, values). The tool turns them into Power BI's URL filter syntax, for example `?filter=Table/Column in ('A','B')`. An "apply to all Entries" button covers the "same pack for each region or month" case.
   - Entries can be reordered by drag and drop, can repeat the same page, and can mix Reports from different Workspaces and Power BI Apps.
3. **Saved Selection**
   - The Selection has a name and is saved as `<name>.json` wherever the User chooses.
   - The file holds the Page URLs, a snapshot of their names, slide titles, Filters, the Slide Layout name and the Render Language. It does not contain the Template.
   - A colleague can open someone else's file.
4. **Export**
   - The User picks the Template (.potx), a Slide Layout (see [Slide composition](#slide-composition) for which one is preselected) and the Render Language (German by default, English possible).
   - An Export holds at most 50 Entries and runs one at a time, with a progress screen.
   - It runs in the **visible Power BI Window**, because the browser profile can't be shared with a second window. The User watches it step through the pages and is asked not to click in it until it's done.
   - Pages are not checked when a Saved Selection is opened. A page that was deleted or can't be accessed becomes an Error Slide during the Export.
5. **Capturing**
   - For each Entry, the Power BI Window opens the Page URL with its Filters.
   - It clicks **"Reset to default"** when Power BI offers it, so persisted personal filters and slicer selections don't leak into the image. The result is the Default State plus the Entry's Filters.
   - It switches the page to **"Fit to page"**, sizes the window to the page, and captures **only the report canvas** at 2× pixel density, without Power BI's header, navigation or panes.
   - The Render Language is set through the browser's language.
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
- **Speaker notes** record the Report and Report Page names, a link back to the page in Power BI, the Filters applied and the Export timestamp.
- A Report Page that fails to render becomes an **Error Slide** that names the page and the reason. The Export carries on.
- Speaker-note labels and Error Slide texts follow the Render Language. The interface itself is English.

## Data handling

- Everything stays on the User's machine. Nothing is sent anywhere except to Power BI itself, and to the update check.
- **Update check:** at startup the tool asks the GitHub releases page whether a newer version exists. It sends no report or user data, only the request any browser would make.
- The Power BI Window's profile holds a live Power BI session. It is as sensitive as a signed-in browser, and "Sign out" deletes it.
- Saved Selections and Decks are files the User keeps.
- Page Images exist only while an Export runs.

## Stack and packaging

- **Tool:** Python 3.12 (managed with `uv`), with Playwright driving the installed browser and python-pptx building the Deck.
- **Interface:** a local web page (TypeScript and React) for the Selection, drag-and-drop and the Export.
- **Packaging:** a single installer, a Windows `.exe` and a macOS `.app`, with everything included and no separate Python install. Installers are unsigned for the internal pilot and code-signed before other organisations get the tool.
- **Code:** a private GitHub repository, with CI on macOS and Windows. The build plan is in [MILESTONE-3.md](MILESTONE-3.md).

## Milestones

1. **Placement prototype.** Done. Uses sample PNGs and real corporate .potx files, and proves the Image Area rules, layout preselection, the Decorative Graphic warning and dropping template slides.
2. **Power BI Window prototype.** Mostly proven on 2026-10-19 on macOS with Chrome, across Workspace, Power BI App and My workspace pages; see [CHECKS.md](../prototype/window/CHECKS.md). Must prove, on Windows and macOS:
   - Signing in with the installed browser and a persistent profile, including MFA and the employer's Conditional Access.
   - "Add current page" reads the Page URL and page name from Workspace, My workspace **and Power BI App** pages.
   - URL filters change the image, also on **Power BI App** pages.
   - "Reset to default" and "Fit to page" can be triggered reliably.
   - Cropping to the report canvas gives a clean 2× image.
   - The Render Language follows the browser language.
3. **The real tool.** Built only after both prototypes pass.
