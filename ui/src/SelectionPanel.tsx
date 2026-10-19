import { FormEvent, useRef, useState } from "react";
import { api, Refused, saveFile } from "./api";
import { EntryItem } from "./EntryItem";
import { Entry, EntryJson, Filter, MAX_ENTRIES, sameFilter, Selection, toJson, withId } from "./types";

type Notice = { kind: "info" | "problem"; text: string } | null;

export function SelectionPanel({
  selection,
  setSelection,
  ready,
  locked,
}: {
  selection: Selection;
  setSelection: (update: (s: Selection) => Selection) => void;
  ready: boolean; // the Power BI Window is open and signed in
  locked: boolean; // an Export is running
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [pasting, setPasting] = useState(false);
  const [address, setAddress] = useState("");
  const [dragged, setDragged] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const entries = selection.entries;
  const full = entries.length >= MAX_ENTRIES;

  async function attempt(action: () => Promise<void>) {
    setBusy(true);
    setNotice(null);
    try {
      await action();
    } catch (e) {
      setNotice({ kind: "problem", text: e instanceof Refused ? e.message : `Something went wrong: ${String(e)}` });
    } finally {
      setBusy(false);
    }
  }

  function append(entry: EntryJson) {
    setSelection((s) => ({ ...s, entries: [...s.entries, withId(entry)] }));
    setNotice({ kind: "info", text: `Added "${entry.pageName}"${entry.reportName ? ` from ${entry.reportName}` : ""}.` });
  }

  const addCurrentPage = () => attempt(async () => append((await api.addCurrentPage()).entry));

  const addByAddress = (event: FormEvent) => {
    event.preventDefault();
    attempt(async () => {
      append((await api.addByAddress(address.trim())).entry);
      setAddress("");
      setPasting(false);
    });
  };

  const update = (id: string, entry: Entry) =>
    setSelection((s) => ({ ...s, entries: s.entries.map((e) => (e.id === id ? entry : e)) }));

  const move = (from: number, to: number) =>
    setSelection((s) => {
      if (to < 0 || to >= s.entries.length || from === to) return s;
      const next = [...s.entries];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return { ...s, entries: next };
    });

  const duplicate = (index: number) =>
    setSelection((s) => {
      const copy = withId({ ...s.entries[index], filters: [...s.entries[index].filters] });
      const next = [...s.entries];
      next.splice(index + 1, 0, copy);
      return { ...s, entries: next };
    });

  const remove = (id: string) => setSelection((s) => ({ ...s, entries: s.entries.filter((e) => e.id !== id) }));

  const applyToAll = (filter: Filter) => {
    setSelection((s) => ({
      ...s,
      entries: s.entries.map((e) => (e.filters.some((f) => sameFilter(f, filter)) ? e : { ...e, filters: [...e.filters, filter] })),
    }));
    setNotice({ kind: "info", text: `Applied the Filter to all ${entries.length} Entries.` });
  };

  const save = () =>
    attempt(async () => {
      const { fileName, content } = await api.saveSelection(toJson(selection));
      saveFile(new Blob([content], { type: "application/json" }), fileName);
      setNotice({ kind: "info", text: `Saved as "${fileName}" in your downloads.` });
    });

  const open = (file: File) =>
    attempt(async () => {
      if (entries.length && !window.confirm(`Replace the current Selection with "${file.name}"?`)) return;
      const { selection: loaded } = await api.openSelection(await file.text());
      setSelection(() => ({ ...loaded, entries: loaded.entries.map(withId) }));
      setNotice({ kind: "info", text: `Opened "${loaded.name}" with ${loaded.entries.length} Entries.` });
    });

  const startNew = () => {
    if (entries.length && !window.confirm("Start a new Selection? Unsaved changes are lost.")) return;
    setSelection(() => ({ name: "Untitled Selection", renderLanguage: selection.renderLanguage, slideLayout: null, entries: [] }));
    setNotice(null);
  };

  return (
    <section className="card">
      <div className="selection-head">
        <label className="name-label">
          <span className="muted small">Selection</span>
          <input
            className="name-input"
            aria-label="Name of this Selection"
            value={selection.name}
            onChange={(e) => setSelection((s) => ({ ...s, name: e.target.value }))}
          />
        </label>
        <div className="file-actions">
          <button type="button" className="quiet" onClick={startNew}>
            New
          </button>
          <button type="button" className="quiet" onClick={() => fileInput.current?.click()}>
            Open…
          </button>
          <button type="button" className="quiet" disabled={busy || !entries.length} onClick={save}>
            Save
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".json,application/json"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) open(file);
            }}
          />
        </div>
      </div>

      <div className="actions">
        <button type="button" disabled={busy || !ready || full || locked} onClick={addCurrentPage}>
          {busy ? "Working…" : "Add current page"}
        </button>
        <button type="button" className="quiet" disabled={busy || !ready || full || locked} onClick={() => setPasting(!pasting)}>
          Paste address
        </button>
        <span className="muted small count">
          {entries.length} of {MAX_ENTRIES} Entries
        </span>
      </div>
      {!ready && <p className="muted small">Sign in in the Power BI Window to add pages.</p>}
      {locked && <p className="muted small">An Export is running. Adding pages and checking Filters wait until it has finished.</p>}
      {full && <p className="muted small">The Selection is full: an Export holds at most {MAX_ENTRIES} Entries.</p>}

      {pasting && (
        <form className="paste-form" onSubmit={addByAddress}>
          <input
            autoFocus
            aria-label="Page address"
            placeholder="https://app.powerbi.com/groups/…/reports/…  or a shared App link"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
          <button type="submit" disabled={busy || !address.trim()}>
            Add
          </button>
        </form>
      )}

      {notice && <p className={notice.kind === "problem" ? "error" : "info"}>{notice.text}</p>}

      {entries.length === 0 ? (
        <p className="muted empty">
          No pages yet. Open a report page in the Power BI Window, then click <strong>Add current page</strong>.
        </p>
      ) : (
        <ol className="entries">
          {entries.map((entry, index) => (
            <EntryItem
              key={entry.id}
              entry={entry}
              position={index}
              count={entries.length}
              canDuplicate={!full}
              onChange={(next) => update(entry.id, next)}
              onMove={(to) => move(index, to)}
              onDuplicate={() => duplicate(index)}
              onRemove={() => remove(entry.id)}
              onApplyFilterToAll={applyToAll}
              canCheck={ready && !locked}
              drag={{
                onDragStart: () => setDragged(index),
                onDragOver: (e) => {
                  e.preventDefault();
                  setOver(index);
                },
                onDrop: () => {
                  if (dragged !== null) move(dragged, index);
                  setDragged(null);
                  setOver(null);
                },
                onDragEnd: () => {
                  setDragged(null);
                  setOver(null);
                },
                over: over === index && dragged !== null && dragged !== index,
              }}
            />
          ))}
        </ol>
      )}
    </section>
  );
}
