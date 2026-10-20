# Changelog

All notable changes to PBI2PPTX are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## Unreleased

- **Open** and **Open with Filters** on each Entry show its page in the Power BI Window for a quick check, without or with the Entry's Filters.

## 0.1.0

The first public version.

- Local tool for macOS and Windows with a browser interface, a menu bar / tray icon and a Power BI Window that uses the installed Chrome or Edge with its own profile.
- Building a Selection with **Add current page** (Workspaces, My workspace and Power BI Apps), pasted page addresses and shared App links; reordering, duplicating and slide titles.
- Filters per Entry: "is one of these values" and Date Filters with fixed dates or Date Rules, taking over the filters set on the page, **Apply to all Entries** and the Filter Overview.
- Filter verification from Power BI's filter pane, with a **Check** button per Filter and Error Slides for Filters Power BI didn't apply.
- Saved Selections as JSON files.
- Export into the user's own `.potx` template: layout recommendation, Decorative Graphic warnings, Image Area placement, optional Filter Box, speaker notes, Error Slides, and German or English number and date formats.
- Unsigned installers: a `.dmg` for macOS and a per-user setup `.exe` for Windows.
