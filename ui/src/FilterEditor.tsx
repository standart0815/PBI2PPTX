import { FormEvent, useState } from "react";
import { describeFilter, Filter } from "./types";

// The Filters of one Entry: list, remove, add, and "Apply to all Entries".
export function FilterEditor({
  filters,
  onChange,
  onApplyToAll,
}: {
  filters: Filter[];
  onChange: (filters: Filter[]) => void;
  onApplyToAll: (filter: Filter) => void;
}) {
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
            <span className="filter-text">{describeFilter(f)}</span>
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
