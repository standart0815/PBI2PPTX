import { FormEvent, useState } from "react";
import { Refused } from "./api";
import { ConditionFields, newDraft, readDraft } from "./ConditionFields";
import { describeFilter } from "./filters";
import type { Filter, FilterCheckResult } from "./types";

type Check = { state: "checking" } | { state: "done"; result: FilterCheckResult } | { state: "error"; message: string };

// The Filters of one Entry: list, remove, add, and "Apply to all Entries".
export function FilterEditor({
  filters,
  onChange,
  onApplyToAll,
  onCheck,
}: {
  filters: Filter[];
  onChange: (filters: Filter[]) => void;
  onApplyToAll: (filter: Filter) => void;
  onCheck: ((filter: Filter) => Promise<FilterCheckResult>) | null; // null while checking isn't possible
}) {
  const [checks, setChecks] = useState<Record<string, Check>>({});
  const key = (f: Filter) => describeFilter(f);

  async function check(f: Filter) {
    if (!onCheck) return;
    setChecks((c) => ({ ...c, [key(f)]: { state: "checking" } }));
    try {
      const result = await onCheck(f);
      setChecks((c) => ({ ...c, [key(f)]: { state: "done", result } }));
    } catch (e) {
      const message = e instanceof Refused ? e.message : String(e);
      setChecks((c) => ({ ...c, [key(f)]: { state: "error", message } }));
    }
  }

  const [table, setTable] = useState("");
  const [column, setColumn] = useState("");
  const [draft, setDraft] = useState(() => newDraft("values", false));

  const condition = readDraft(draft);
  const complete = table.trim() && column.trim() && !("problem" in condition);

  function add(event: FormEvent) {
    event.preventDefault();
    if (!complete || "problem" in condition) return;
    const field = { table: table.trim(), column: column.trim() };
    if (condition.kind === "values") {
      onChange([...filters, { ...field, values: condition.values }]);
    } else {
      // A single Entry's form has no "keep as is", so both ends are DateEnds here.
      onChange([...filters, { ...field, from: condition.from === "keep" ? null : condition.from, to: condition.to === "keep" ? null : condition.to }]);
    }
    setDraft({ ...draft, values: "" });
  }

  return (
    <div className="filters">
      {filters.length === 0 && <p className="muted">No Filters: the page is captured as published.</p>}
      <ul className="filter-list">
        {filters.map((f, i) => (
          <li key={i}>
            <span className="filter-text">
              {describeFilter(f)}
              <CheckResult check={checks[key(f)]} />
            </span>
            <button type="button" className="link" disabled={!onCheck || checks[key(f)]?.state === "checking"} onClick={() => check(f)}>
              Check
            </button>
            <button type="button" className="link" onClick={() => onApplyToAll(f)}>
              Apply to all Entries
            </button>
            <button type="button" className="link danger" onClick={() => onChange(filters.filter((_, j) => j !== i))}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      <form className="filter-form" onSubmit={add}>
        <label>
          Table
          <input value={table} onChange={(e) => setTable(e.target.value)} placeholder="financials" />
        </label>
        <label>
          Column
          <input value={column} onChange={(e) => setColumn(e.target.value)} placeholder="Country" />
        </label>
        <ConditionFields draft={draft} onChange={setDraft} allowKeep={false} />
        <button type="submit" disabled={!complete}>
          Add Filter
        </button>
      </form>
      {"problem" in condition && draft.kind === "date" && (draft.from.choice !== "none" || draft.to.choice !== "none") && (
        <p className="warning small">{condition.problem}</p>
      )}
      <p className="muted small">
        Use the table and column names from the report's data. A value made only of digits is treated as a number. A date
        range needs a real date column, such as Calendar / Date; both ends count in full.
      </p>
    </div>
  );
}

function CheckResult({ check }: { check: Check | undefined }) {
  if (!check) return null;
  if (check.state === "checking") return <span className="check muted small">Checking in the Power BI Window…</span>;
  if (check.state === "error") return <span className="check error small">{check.message}</span>;
  const { result, message } = check.result;
  const tone = result === "applied" ? "info" : result === "not applied" ? "error" : "warning";
  const mark = result === "applied" ? "✓" : result === "not applied" ? "✗" : "?";
  return (
    <span className={`check small ${tone}`}>
      {mark} {message}
    </span>
  );
}
