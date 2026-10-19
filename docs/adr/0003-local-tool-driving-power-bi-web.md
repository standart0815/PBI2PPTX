# A local tool that drives app.powerbi.com, with no Entra app registration

Supersedes [ADR 0001](0001-render-pages-by-embedding-not-export-api.md) and [ADR 0002](0002-server-stores-nothing.md).

PBI2PPTX is a desktop tool for Windows and macOS. It opens Power BI in a browser window that it controls (the Power BI Window), where the User signs in to app.powerbi.com with their own credentials, exactly as they normally would. Page Images are captured from that window. The tool has no Entra app registration and calls no Power BI API.

We chose this for three reasons:
- Users from **any organisation** can use it.
- **No admin**, in our tenant or in theirs, has to register or approve anything.
- We own and maintain **no Azure or Entra component**.

## Considered Options

- **Hosted app with a single-tenant registration** (the original design, ADR 0001). Rejected because it needs our admin and only serves our own organisation.
- **Hosted app with one multi-tenant registration.** This was supported, stable and worked for other organisations. Rejected because it still leaves an Entra component to own, and organisations that block user consent would need their admin to approve once.
- **Borrowing a Microsoft first-party client ID.** Rejected because it is unsupported: it can break without notice or be blocked by Conditional Access.
- **A hosted app driving app.powerbi.com.** Rejected because the server would have to run other people's interactive Microsoft sign-ins in a remote browser.

## Consequences

- **Brittleness.** The tool depends on how the Power BI web interface looks and behaves, which Microsoft can change without notice. That includes the report canvas, "Reset to default" and the "Fit to page" view. Expect maintenance after Power BI releases.
- **No listing of reports or pages.** Entries are added from whatever page is showing in the Power BI Window, or from a pasted Page URL. Filters become Power BI URL filters, and their support on Power BI App URLs is unconfirmed.
- **Each User installs it.** It uses the browser already installed on the machine.
- **What is stored, and where:** everything stays on the User's machine. The Power BI Window keeps a persistent browser profile holding a live Power BI session; "Sign out" deletes it. Saved Selections are files the User keeps. Page Images exist only during an Export. Nothing is sent anywhere except to Power BI itself.
