---
status: superseded by ADR-0003
---

# Render Report Pages by embedding them, not through the Export API

Reports may sit on shared (Pro-only) or Premium Per User capacity, and many Users reach Reports only through a Power BI App. So every Page Image is produced the same way. The server embeds the Report Page with Microsoft's `powerbi-client` JavaScript SDK in a headless browser, using the signed-in User's delegated token, hides the filter and navigation panes, and captures the image once the SDK reports the page as rendered. The Power BI Export To File API is not used, even for Reports where capacity exists.

## Considered Options

- **Export To File API.** Rejected:
  - It only works on Premium, Embedded or Fabric capacity, and every semantic model behind the Report must be there too. PPU is not supported.
  - It has no Power BI App–scoped variant.
  - Its native PPTX output can't use a custom Template.
  - PNG export needs a tenant setting that is off by default.
- **Hybrid: the Export API where capacity exists, embedding elsewhere.** Rejected because it means two rendering paths to maintain, and Page Images in one Deck would look different depending on where each Report lives.
- **Screenshotting app.powerbi.com directly.** Rejected. It relies on undocumented URL parameters to hide the Power BI interface and breaks whenever that interface changes.

## Consequences

- It is unconfirmed whether embedding works for a User whose only access to a Report is through a Power BI App. This is the first thing to prove in a prototype.
- No API lists the pages of a Report reached through a Power BI App, so page listing (including spotting Hidden Pages) also goes through the SDK.
- The tenant's embedding setting ("Embed content in apps") must allow these Users. This needs to be verified in the prototype.
- The server needs a headless browser, and it holds the User's Power BI token for the duration of an Export.
