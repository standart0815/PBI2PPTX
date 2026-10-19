import { useCallback, useEffect, useState } from "react";
import { api, Refused, saveFile } from "./api";
import { describeFilter, EntryProgress, ExportProgress, MAX_ENTRIES, Selection, TemplateInfo, toJson } from "./types";

const MARK: Record<EntryProgress["state"], string> = {
  waiting: "·",
  capturing: "…",
  captured: "✓",
  "not verified": "?",
  "error slide": "✗",
};

export function ExportPanel({
  selection,
  template,
  signedIn,
  onRunningChange,
}: {
  selection: Selection;
  template: TemplateInfo | null;
  signedIn: boolean;
  onRunningChange: (running: boolean) => void;
}) {
  const [progress, setProgress] = useState<ExportProgress | null>(null);
  const [deckReady, setDeckReady] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const running = progress?.state === "running";

  const refresh = useCallback(async () => {
    try {
      const { export: p, deckReady: ready } = await api.exportStatus();
      setProgress(p);
      setDeckReady(ready);
    } catch {
      // the status card already says when PBI2PPTX isn't running
    }
  }, []);

  useEffect(() => {
    refresh(); // an Export may already be running, e.g. after reloading this tab
  }, [refresh]);

  useEffect(() => {
    onRunningChange(running);
    if (!running) return;
    const timer = window.setInterval(refresh, 1000);
    return () => window.clearInterval(timer);
  }, [running, refresh, onRunningChange]);

  const missing = [
    !selection.entries.length && "add at least one page",
    selection.entries.length > MAX_ENTRIES && `keep it to ${MAX_ENTRIES} Entries`,
    !template && "choose a template",
    !signedIn && "sign in to Power BI",
  ].filter(Boolean) as string[];

  async function start() {
    setProblem(null);
    try {
      await api.startExport(toJson(selection));
      await refresh();
    } catch (e) {
      setProblem(e instanceof Refused ? e.message : String(e));
    }
  }

  async function download() {
    setProblem(null);
    try {
      const { blob, fileName } = await api.downloadDeck();
      saveFile(blob, fileName);
    } catch (e) {
      setProblem(e instanceof Refused ? e.message : String(e));
    }
  }

  const entries = progress?.entries ?? [];
  const finished = entries.filter((e) => !["waiting", "capturing"].includes(e.state)).length;
  const count = (state: EntryProgress["state"]) => entries.filter((e) => e.state === state).length;

  return (
    <section className="card">
      <h2>Export</h2>

      {!running && (
        <>
          {missing.length > 0 ? (
            <p className="muted">Before exporting, {missing.join(", ")}.</p>
          ) : (
            <p className="muted">
              {selection.entries.length} page{selection.entries.length === 1 ? "" : "s"} into <strong>{template?.fileName}</strong>,
              layout <strong>{selection.slideLayout}</strong>, {selection.renderLanguage === "de-DE" ? "Deutsch" : "English"}. The
              Power BI Window steps through the pages; please don't click in it meanwhile.
            </p>
          )}
          <div className="actions">
            <button type="button" disabled={missing.length > 0} onClick={start}>
              Export Deck
            </button>
          </div>
        </>
      )}

      {running && progress && (
        <>
          <p>{progress.phase || "Working…"}</p>
          <progress className="bar" max={entries.length} value={finished} aria-label="Export progress" />
          <div className="actions">
            <button type="button" className="quiet" onClick={() => api.cancelExport()}>
              Cancel after this page
            </button>
          </div>
        </>
      )}

      {problem && <p className="error">{problem}</p>}
      {progress?.state === "failed" && <p className="error">{progress.error}</p>}
      {progress?.state === "cancelled" && <p className="muted">The Export was cancelled. No Deck was made.</p>}

      {progress?.state === "done" && (
        <div className="result">
          <p>
            <strong>{progress.file_name}</strong> is ready: {count("captured")} captured
            {count("not verified") > 0 && `, ${count("not verified")} with Filters not verified`}
            {count("error slide") > 0 && `, ${count("error slide")} Error Slide${count("error slide") === 1 ? "" : "s"}`}.
          </p>
          <div className="actions">
            <button type="button" disabled={!deckReady} onClick={download}>
              Download Deck
            </button>
          </div>
          {!deckReady && <p className="muted small">The Deck is no longer kept. Export again to get it.</p>}
        </div>
      )}

      {entries.length > 0 && progress?.state !== "idle" && (
        <ol className="export-entries">
          {entries.map((e, i) => (
            <li key={i} className={`export-entry ${e.state.replace(" ", "-")}`}>
              <span className="mark" aria-hidden="true">
                {MARK[e.state]}
              </span>
              <div>
                <span>{e.title}</span>
                {e.filters.length > 0 && <span className="muted small"> · {e.filters.map(describeFilter).join("; ")}</span>}
                {e.message && <p className="small entry-message">{e.message}</p>}
              </div>
              {e.seconds > 0 && <span className="muted small">{e.seconds} s</span>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
