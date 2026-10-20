import { FormEvent, useState } from "react";
import { Refused } from "./api";
import { describeFilter, Filter, FilterCheckResult } from "./types";

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
  const [values, setValues] = useState("");

  const parsed = values.split(",").map((v) => v.trim()).filter(Boolean);
  const complete = table.trim() && column.trim() && parsed.length > 0;

  function add(event: FormEvent) {
    event.preventDefault();
    if (!complete) return;
    onChange([...filters, { table: table.trim(), column: column.trim(), values: parsed }]);
    setValues("");
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
        <label className="wide">
          Values, separated by commas
          <input value={values} onChange={(e) => setValues(e.target.value)} placeholder="Germany, France" />
        </label>
        <button type="submit" disabled={!complete}>
          Add Filter
        </button>
      </form>
      <p className="muted small">
        Use the table and column names from the report's data. A value made only of digits is treated as a number.
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
