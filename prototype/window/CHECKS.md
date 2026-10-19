# Milestone 2: Power BI Window checks

Run these checks yourself; only you can sign in. Start from `prototype/window`:

```bash
../.venv/bin/python spike.py
```

Chrome (Edge on Windows) opens with its own profile. Sign in there as you normally would. Then type commands in the terminal. `help` lists them.

You'll need:
- one report page in a **Workspace**,
- one in **My workspace** (if you have one),
- one you reach **only through a Power BI App**,
- a column whose values you know, for the Filter test.

| # | Check | How | Passes when |
|---|---|---|---|
| 1 | Sign-in with MFA and Conditional Access | Sign in within the Power BI Window | You reach the Power BI home page |
| 2 | Session is kept | `quit`, then start `spike.py` again | Power BI opens with no new sign-in |
| 3 | "Add current page" works for every route | Open each page, type `add` | It prints the right **page name** and says `Workspace`, `My workspace` or `Power BI App` |
| 4 | Capture plus Deck | `export ../placement/samples/sample-header-footer.potx` | The Deck in `out/` shows the report canvas only (no Power BI header or panes), sharp, with German number formats |
| 5 | Filters work, **also on the Power BI App page** | `add` the same page twice, `filter 2 Table/Column=Value`, `export …` | Slide 2 shows filtered numbers and slide 1 doesn't |
| 6 | "Reset to default" | Change a slicer on a page by hand, then `export …` | The export log says `reset: clicked`, and the image shows the default slicer state |
| 7 | "Fit to page" | Look at the export log | It says `fit to page: set` |
| 8 | No access becomes an Error Slide | `add` a URL with a made-up report ID, then `export …` | That Entry becomes an Error Slide and the export carries on |
| 9 | Render Language | `quit`, start with `--lang en-US`, then `export …` | Number formats switch to English |
| 10 | Sign out | `signout`, then start again | Power BI asks you to sign in |

## If something fails

The page name, canvas, "Reset to default" and "Fit to page" all depend on the Power BI interface. If any of them fails, open the page in question and type `probe`. It lists the large page elements and all buttons and menu items. Send me that output, and I'll adjust `CANVAS_SELECTORS` and the button texts in [pbi_window.py](pbi_window.py).

Two more things to watch for:
- **Number filters.** A value made only of digits is sent unquoted (`Year eq 2026`). If the column is text, that filter fails silently. Note it if you see it.
- **Windows.** This was built and launch-tested only on macOS with Chrome. Run checks 1–4 on a Windows machine with Edge too.

## Results, 2026-10-19 (macOS, Chrome, run by `run_checks.py`)

The first runs used only **My workspace** (report "Example"). The run at 18:43 added the same report in a **Workspace** and in a **Power BI App**.

| # | Result | Notes |
|---|---|---|
| 1 | PASS | Sign-in with MFA in the Power BI Window. Answered "Stay signed in?" with Yes. |
| 2 | PASS | Restarting opens Power BI home without a new sign-in. |
| 3 | PASS for all three routes | Page name "Example" and the route are read correctly. In an App, the page name comes from the App's own navigation. |
| 4 | PASS | Clean 2626×1476 px canvas: no Power BI header or panes, no tips, no visual toolbars. German formats. |
| 5 | PASS for all three routes, **including the Power BI App** | `financials/Country=Germany` reduces the totals from 118.726.350,26 to 23.505.340,82. |
| 6 | PASS (result) | A changed slicer doesn't reach the image: the capture matches the Default State exactly. This report doesn't keep slicer selections, so the reset itself wasn't needed here. Confirming the reset dialog worked in an earlier run. |
| 7 | PASS | The canvas was already in fit-to-page view (`displayArea.fitToPage`). |
| 8 | PASS | A made-up report becomes an Error Slide, and the Export carries on. |
| 9 | PASS | en-US gives `13,815,307.89`, `1/1/2013`, "Total". Month names stored in the data stay German. |
| 10 | Not run | It would delete the signed-in session. |

Fixes found during the run, now in [pbi_window.py](pbi_window.py):
- **Page name:** read from the pages pane, not the first selected tab (that was the ribbon).
- **Reset:** confirm inside the dialog. Reset on the plain page, then open the page with Filters.
- **Tips and toolbars:** dismiss Power BI's `tutorial-popup` tips, hide the visuals' hover toolbars (`.optionsMenu`), and move focus away from the visuals.
- **Capture:** clip the page instead of taking an element screenshot, which kept timing out.
- **Waiting:** don't wait for "network idle", which Power BI may never reach. Wait for the canvas instead.
- **Restarts:** wait until Chrome releases the profile lock before relaunching.
- **App page name:** read from the App's navigation (`aria-current="page"`), which has no pages pane.
- **App links:** a shared App link (`/Redirect?action=OpenApp&appId=…`) is not a Page URL. Opening it in the Power BI Window resolves it to `groups/me/apps/{app}/reports/{report}/{page}`.

**Still open:**
- **A User with App-only access.** The test account can also open the Workspace, so a User who reaches the report only through the App is still unproven. It is very likely to work, because the tool uses only what the App page itself shows.
- **Resetting saved personal filters.** This report doesn't keep slicer selections, so there was nothing saved to reset.
- **Windows with Edge.**
