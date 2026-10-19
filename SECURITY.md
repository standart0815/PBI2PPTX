# Security policy

PBI2PPTX holds a live Power BI session in its browser profile and runs a local server, so security problems matter. Thank you for reporting them responsibly.

## Reporting a vulnerability

Please **don't open a public issue**. Report it privately through GitHub instead: on the repository's **Security** tab, choose **Report a vulnerability**. Include what an attacker could do, the steps to reproduce it, and the PBI2PPTX version and operating system.

You can expect a first answer within a week. Fixes go into the next release, and the advisory is published once that release is out.

## Supported versions

Only the latest release gets security fixes.

## What is in scope

- The local server: it listens on `127.0.0.1` only and accepts API calls only with the token that changes with every start.
- The Power BI Window's browser profile, which holds the user's Power BI session, and **Sign out**, which deletes it.
- Files PBI2PPTX reads or writes: Templates, Saved Selections, Decks and its log file.

Problems in Power BI itself, in Chrome or Edge, or in the user's Microsoft account belong with their vendors.
