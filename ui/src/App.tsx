import { useCallback, useEffect, useState } from "react";
import { api, NotRunning, Status } from "./api";
import { ExportPanel } from "./ExportPanel";
import { SelectionPanel } from "./SelectionPanel";
import { TemplatePanel } from "./TemplatePanel";
import { emptySelection, Selection, TemplateInfo } from "./types";

// The Selection survives a reload of this tab, and nothing more (sessionStorage).
const STORAGE_KEY = "pbi2pptx-selection";

function loadStoredSelection(): Selection {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    return stored ? (JSON.parse(stored) as Selection) : emptySelection();
  } catch {
    return emptySelection();
  }
}

type Phase = "running" | "stopped" | "unreachable";

export function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [phase, setPhase] = useState<Phase>("running");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelectionState] = useState<Selection>(loadStoredSelection);
  const [template, setTemplate] = useState<TemplateInfo | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    // The server keeps the picked Template for this run, so a reload can show it again.
    api.getTemplate().then((r) => r.template && setTemplate(r.template)).catch(() => undefined);
  }, []);

  const setSelection = useCallback((update: (s: Selection) => Selection) => {
    setSelectionState((current) => {
      const next = update(current);
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // storage unavailable: the Selection simply won't survive a reload
      }
      return next;
    });
  }, []);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.status());
      setPhase("running");
    } catch (e) {
      if (e instanceof NotRunning) setPhase((p) => (p === "stopped" ? p : "unreachable"));
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 1500);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function run(label: string, action: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function quit() {
    const unsaved = selection.entries.length ? " Save your Selection first if you want to keep it." : "";
    if (!window.confirm(`Quit PBI2PPTX? The Power BI Window closes too.${unsaved}`)) return;
    await api.quit().catch(() => undefined);
    setPhase("stopped");
  }

  const signedIn = status?.window.state === "open" && status.window.signed_in;

  if (phase === "stopped") {
    return (
      <main className="page">
        <h1>PBI2PPTX</h1>
        <p className="lead">PBI2PPTX has stopped. You can close this tab.</p>
      </main>
    );
  }

  if (phase === "unreachable") {
    return (
      <main className="page">
        <h1>PBI2PPTX</h1>
        <p className="lead">PBI2PPTX isn't running. Start it again from its icon or command.</p>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="top">
        <h1>PBI2PPTX</h1>
        <span className="muted">{status ? `Version ${status.version}` : ""}</span>
      </header>

      <WindowCard status={status} busy={busy} run={run} />
      {error && <p className="error">Something went wrong: {error}</p>}

      <SelectionPanel
        selection={selection}
        setSelection={setSelection}
        ready={signedIn}
        locked={exporting}
      />

      <TemplatePanel template={template} setTemplate={setTemplate} selection={selection} setSelection={setSelection} />

      <ExportPanel selection={selection} template={template} signedIn={signedIn} onRunningChange={setExporting} />

      <footer className="bottom">
        <button className="quiet" onClick={quit}>
          Quit PBI2PPTX
        </button>
      </footer>
    </main>
  );
}

function WindowCard({
  status,
  busy,
  run,
}: {
  status: Status | null;
  busy: string | null;
  run: (label: string, action: () => Promise<unknown>) => void;
}) {
  const w = status?.window;
  let tone = "neutral";
  let headline = "Opening the Power BI Window…";
  let hint = "";

  if (w?.state === "open" && w.signed_in) {
    tone = "ok";
    headline = "Signed in to Power BI";
    hint = "Browse to the pages you want in the Power BI Window.";
  } else if (w?.state === "open") {
    tone = "attention";
    headline = "Sign in to Power BI in the Power BI Window";
    hint = "Use your own Microsoft work account. PBI2PPTX never sees your password.";
  } else if (w?.state === "closed") {
    headline = "The Power BI Window is closed";
    hint = "Reopen it to continue.";
  } else if (w?.state === "failed") {
    tone = "problem";
    headline = "The Power BI Window could not open";
    hint = `${w.message} PBI2PPTX needs Microsoft Edge or Google Chrome.`;
  }

  const open = w?.state === "open";
  return (
    <section className={`card status ${tone}`} aria-live="polite">
      <div className="status-line">
        <span className="dot" aria-hidden="true" />
        <div>
          <h2>{headline}</h2>
          {hint && <p className="muted">{hint}</p>}
        </div>
      </div>
      <div className="actions">
        <button disabled={!!busy || w?.state === "starting"} onClick={() => run("show", api.showWindow)}>
          {busy === "show" ? "Opening…" : open ? "Show Power BI Window" : "Reopen Power BI Window"}
        </button>
        {open && w?.signed_in && (
          <button
            className="quiet"
            disabled={!!busy}
            onClick={() =>
              window.confirm("Sign out of Power BI? You'll have to sign in again next time.") &&
              run("signout", api.signOut)
            }
          >
            {busy === "signout" ? "Signing out…" : "Sign out"}
          </button>
        )}
      </div>
    </section>
  );
}
