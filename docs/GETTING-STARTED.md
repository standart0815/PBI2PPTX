# Starting PBI2PPTX

This manual covers version 0.1.0, which is still in development. It starts, signs you in to Power BI and shows your sign-in status. **Adding pages and exporting a Deck come in the next versions** (Milestone 3, steps 4–6). Until the installers exist (step 7), you start it from the project folder with a command.

Terms such as *Power BI Window*, *Selection* and *Deck* are explained in [GLOSSARY.md](../GLOSSARY.md).

## What you need

- **macOS or Windows**
- **Google Chrome or Microsoft Edge**, installed as usual. PBI2PPTX uses it for the Power BI Window. Edge is preferred on Windows and Chrome on macOS.
- **[uv](https://docs.astral.sh/uv/)**, which installs the right Python by itself.
- **[Node.js](https://nodejs.org/)** 22 or newer, only for building the interface once.

## First-time setup

In a terminal, in the project folder:

```bash
uv sync
npm --prefix ui install
npm --prefix ui run build
```

Repeat the last two commands whenever the interface (`ui/`) has changed.

## Starting

```bash
uv run pbi2pptx
```

Two windows open:

1. **The PBI2PPTX interface**, in your default browser. Everything is controlled from here.
2. **The Power BI Window**, a Chrome or Edge window with its own profile, separate from your normal browser. It opens Power BI.

The terminal shows the interface's address. It contains a secret that changes with every start, so an old bookmark won't work. Start PBI2PPTX again instead.

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
- **Quit PBI2PPTX** closes the Power BI Window and stops the tool. Pressing **Ctrl+C** in the terminal does the same.

## Options

```bash
uv run pbi2pptx --no-open      # don't open the interface automatically; open the printed address yourself
uv run pbi2pptx --port 8765    # use a fixed port instead of any free one
uv run pbi2pptx --version
```

## What is stored, and where

Only the Power BI Window's profile, which includes your Power BI session:

- **macOS:** `~/Library/Application Support/PBI2PPTX/profile`
- **Windows:** `%LOCALAPPDATA%\PBI2PPTX\profile`

**Sign out** deletes it. Nothing is sent anywhere except to Power BI.

## Troubleshooting

| You see | Cause | Fix |
|---|---|---|
| "The interface isn't built yet" | The interface build is missing. | Run `npm --prefix ui install` and `npm --prefix ui run build`, then reload. |
| "Please start PBI2PPTX from its icon or command" | An address from an earlier start. | Start PBI2PPTX again and use the new address. |
| "PBI2PPTX isn't running" | The tool was quit, or the terminal was closed. | Start it again. |
| The start takes up to 30 seconds | The Power BI Window from the last run is still closing. | Wait. PBI2PPTX waits for it. |
| Power BI asks you to sign in every time | You answered "No" to "Stay signed in?", or your company doesn't allow it. | Answer Yes. If your company forbids it, you'll sign in on every start. |
