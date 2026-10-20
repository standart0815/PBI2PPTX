"""Everything that depends on how the Power BI web interface looks (ADR 0003).

Microsoft can change the interface without notice. When capturing breaks after a Power BI
release, this is the one file to fix. `python -m pbi2pptx.self_check` shows what broke, and
tests/fixtures/fake_power_bi.html mirrors these selectors for the offline tests, so update it too.

Texts are listed per interface language (German, English). Selectors are preferred where
Power BI offers language-independent ones.
"""

HOME = "https://app.powerbi.com/home"

# Where Power BI sends a browser that is not signed in.
SIGNED_OUT_MARKERS = ("login.microsoftonline.com", "login.live.com", "/singleSignOn", "/signin")

# The report canvas. Its class list carries "fitToPage" when the page is in fit-to-page view.
CANVAS = "div.displayArea"
FIT_TO_PAGE_CLASS = "fitToPage"

# The current page's display name, tried in order.
CURRENT_PAGE_NAME = (
    # Workspace reports: the pages pane, not the ribbon (whose tabs are also role=tab).
    "exploration-fluent-navigation [role='tab'][aria-selected='true']",
    "section.newLookPageNav [role='tab'][aria-selected='true']",
    # Power BI Apps: the App's own navigation, where the current page is a link.
    "mat-list div.itemRow[role='link'][aria-current='page']",
)
# The report name: the header's report button carries it as its label, in Workspaces and Apps.
REPORT_NAME = "button.info-bar"
# Fallback, the browser tab title: "<Page> - <Report> – Power BI" in Workspaces, "<Report> – Power BI" in Apps.
TITLE_SUFFIX_SEPARATOR = " – "
TITLE_PAGE_SEPARATOR = " - "

# "Reset to default" in the report ribbon, and its confirmation dialog.
RESET_BUTTON_TEXTS = ("Auf Standardwert zurücksetzen", "Auf Standard zurücksetzen", "Reset to default")
DIALOGS = "[role=dialog], [role=alertdialog]"
RESET_CONFIRM_TEXTS = ("Zurücksetzen", "Reset")  # exact, inside the dialog

# Fit to page: the "View" ribbon tab, then the "Fit to page" command.
VIEW_TAB_TEXTS = ("Anzeigen", "View")
FIT_TO_PAGE_TEXTS = ("An Seite anpassen", "Seite anpassen", "Fit to page")

# Tips and promotions laid over the canvas.
OVERLAYS = (".tutorial-popup", ".ms-TeachingBubble", "[role=dialog]", "[role=alertdialog]")
TUTORIAL_DISMISS = ".tutorial-popup button.cancel"  # "Vielleicht später" / "Maybe later"
DISMISS_TEXTS = ("Vielleicht später", "Maybe later", "Nicht jetzt", "Not now", "Verstanden", "Got it", "Schließen", "Close")

# Loading indicators to wait out.
SPINNERS = (".circle-spinner", ".powerbi-spinner")

# Injected before capturing: the icon toolbars visuals show on hover or focus (not their titles).
CAPTURE_CSS = ".optionsMenu, visual-container-options-menu { visibility: hidden !important; }"
