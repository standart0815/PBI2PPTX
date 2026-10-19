import { FormEvent, useState } from "react";
import { ConditionDraft, ConditionFields, newDraft, readDraft } from "./ConditionFields";
import { describeCondition, editFilters, FieldGroup, groupByField, isDateFilter, removeFilters, sameFilter } from "./filters";
import type { Entry, Filter } from "./types";

// Every Filter of the Selection, grouped by field. Filters of one field can be selected across
// Entries and edited or removed together (DESIGN.md, Filter Overview).

type Notice = { kind: "info" | "problem"; text: string } | null;

export function FilterOverview({ entries, onChange }: { entries: Entry[]; onChange: (entries: Entry[]) => void }) {
  // Each selected Filter is remembered with what it was, so a Filter that changed or moved in its
  // Entry meanwhile drops out of the selection instead of another one being edited by mistake.
  const [picked, setPicked] = useState<Map<string, Filter>>(new Map());
  const [draft, setDraft] = useState<ConditionDraft | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  const groups = groupByField(entries);
  const items = groups.flatMap((g) => g.items);
  const selected = new Set(items.filter((i) => picked.has(i.ref) && sameFilter(picked.get(i.ref)!, i.filter)).map((i) => i.ref));
  const group = groups.find((g) => g.items.some((i) => selected.has(i.ref)));
  const filterCount = items.length;

  function choose(next: Map<string, Filter>) {
    setPicked(next);
    setDraft(null);
    setNotice(null);
  }

  function toggle(g: FieldGroup, ref: string, filter: Filter, on: boolean) {
    // Selection works within one field: a tick in another field starts over there.
    const next = new Map(group && group.key !== g.key ? [] : [...picked].filter(([r]) => selected.has(r)));
    if (on) next.set(ref, filter);
    else next.delete(ref);
    choose(next);
  }

  function toggleAll(g: FieldGroup, on: boolean) {
    choose(on ? new Map(g.items.map((i) => [i.ref, i.filter])) : new Map());
  }

  function startEdit(g: FieldGroup) {
    const chosen = g.items.filter((i) => selected.has(i.ref)).map((i) => i.filter);
    const dated = chosen.every(isDateFilter);
    const start = newDraft(dated ? "date" : "values", true);
    const values = chosen.map((f) => (isDateFilter(f) ? "" : f.values.join(", ")));
    if (!dated && values.every((v) => v === values[0])) start.values = values[0];
    setDraft(start);
    setNotice(null);
  }

  function apply(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    const condition = readDraft(draft);
    if ("problem" in condition) {
      setNotice({ kind: "problem", text: condition.problem });
      return;
    }
    const result = editFilters(entries, selected, condition);
    if ("problem" in result) {
      setNotice({ kind: "problem", text: result.problem });
      return;
    }
    onChange(result.entries);
    choose(new Map());
    setNotice({ kind: "info", text: `Changed ${selected.size} Filter${selected.size === 1 ? "" : "s"}.` });
  }

  function remove() {
    const count = selected.size;
    if (!window.confirm(`Remove ${count} Filter${count === 1 ? "" : "s"} from their Entries?`)) return;
    onChange(removeFilters(entries, selected));
    choose(new Map());
    setNotice({ kind: "info", text: `Removed ${count} Filter${count === 1 ? "" : "s"}.` });
  }

  const condition = draft ? readDraft(draft) : null;

  return (
    <details className="overview">
      <summary>
        <strong>Filter Overview</strong>
        <span className="muted small">
          {" "}
          · {filterCount} Filter{filterCount === 1 ? "" : "s"} on {groups.length} field{groups.length === 1 ? "" : "s"}
        </span>
      </summary>
      <p className="muted small">Tick Filters of one field to edit or remove them on all their Entries at once.</p>
      {notice && <p className={`small ${notice.kind === "problem" ? "error" : "info"}`}>{notice.text}</p>}

      {groups.map((g) => {
        const ticked = g.items.filter((i) => selected.has(i.ref)).length;
        const active = group?.key === g.key;
        return (
          <div key={g.key} className={`field-group${active ? " active" : ""}`}>
            <label className="group-head">
              <input
                type="checkbox"
                aria-label={`Select all Filters on ${g.table} / ${g.column}`}
                checked={ticked === g.items.length}
                ref={(box) => {
                  if (box) box.indeterminate = ticked > 0 && ticked < g.items.length;
                }}
                onChange={(e) => toggleAll(g, e.target.checked)}
              />
              <strong>
                {g.table} / {g.column}
              </strong>
              <span className="muted small">
                {g.entryCount} Entr{g.entryCount === 1 ? "y" : "ies"}
              </span>
            </label>
            <ul className="overview-items">
              {g.items.map((i) => (
                <li key={i.ref}>
                  <label>
                    <input type="checkbox" checked={selected.has(i.ref)} onChange={(e) => toggle(g, i.ref, i.filter, e.target.checked)} />
                    <span className="position">{i.position + 1}</span>
                    <span>{i.entry.slideTitle}</span>
                    <span className="muted"> · {describeCondition(i.filter)}</span>
                  </label>
                </li>
              ))}
            </ul>

            {active && !draft && (
              <div className="actions overview-actions">
                <span className="small">{ticked} selected</span>
                <button type="button" onClick={() => startEdit(g)}>
                  Edit selected
                </button>
                <button type="button" className="quiet danger" onClick={remove}>
                  Remove selected
                </button>
                <button type="button" className="quiet" onClick={() => choose(new Map())}>
                  Clear selection
                </button>
              </div>
            )}
            {active && draft && (
              <form className="filter-form overview-edit" onSubmit={apply}>
                <ConditionFields draft={draft} onChange={setDraft} allowKeep />
                <button type="submit" disabled={!!condition && "problem" in condition}>
                  Apply to {ticked} Filter{ticked === 1 ? "" : "s"}
                </button>
                <button type="button" className="quiet" onClick={() => setDraft(null)}>
                  Cancel
                </button>
                {condition && "problem" in condition && <p className="warning small">{condition.problem}</p>}
              </form>
            )}
          </div>
        );
      })}
    </details>
  );
}
