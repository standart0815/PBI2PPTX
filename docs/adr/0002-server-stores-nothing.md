---
status: superseded by ADR-0003
---

# The server stores nothing

The server keeps no User data at rest:
- Saved Selections are JSON files that the User downloads and uploads again.
- The Template is uploaded with every Export.
- Page Images and Decks exist only while an Export runs, and are deleted after download or after at most one hour.
- Power BI tokens live only in the User's server-side session.
- Logs contain no report content.

We chose this so the tool holds no report data or tokens that could leak, adds no data-protection or retention scope, and has no database or file storage to run. A database for Saved Selections or a shared Template library would be convenient, but both are deliberately left out.
