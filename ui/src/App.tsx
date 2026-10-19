import { useCallback, useEffect, useState } from "react";
import { api, NotRunning, Status } from "./api";

type Phase = "running" | "stopped" | "unreachable";

export function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [phase, setPhase] = useState<Phase>("running");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    if (!window.confirm("Quit PBI2PPTX? The Power BI Window closes too.")) return;
    await api.quit().catch(() => undefined);
    setPhase("stopped");
  }

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

      <section className="card">
        <h2>Selection</h2>
        <p className="muted">No pages yet.</p>
        <button disabled title="Arrives in the next version">
          Add current page
        </button>
      </section>

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
