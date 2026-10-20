import { DATE_RULES, rangeProblem } from "./filters";
import type { Condition, EndEdit } from "./filters";
import type { DateEnd, DateRule } from "./types";

// The condition part of a Filter, shared by the Filter form and "Edit selected" in the Filter
// Overview: values, or a date range whose ends are none, a fixed date or a Date Rule. Only "Edit
// selected" offers "keep as is" for an end (DESIGN.md, Filter Overview).

export type EndChoice = "keep" | "none" | "date" | DateRule;

export interface EndDraft {
  choice: EndChoice;
  date: string; // "YYYY-MM-DD" from the date picker, used when choice is "date"
}

export interface ConditionDraft {
  kind: "values" | "date";
  values: string; // comma-separated, as typed
  from: EndDraft;
  to: EndDraft;
}

export function newDraft(kind: ConditionDraft["kind"], keep: boolean): ConditionDraft {
  const end: EndDraft = { choice: keep ? "keep" : "none", date: "" };
  return { kind, values: "", from: end, to: end };
}

/** The Condition the draft describes, or why it isn't complete yet. */
export function readDraft(draft: ConditionDraft): Condition | { problem: string } {
  if (draft.kind === "values") {
    const values = draft.values.split(",").map((v) => v.trim()).filter(Boolean);
    return values.length ? { kind: "values", values } : { problem: "Enter at least one value." };
  }
  const read = (end: EndDraft, name: string): EndEdit | { problem: string } => {
    if (end.choice === "keep") return "keep";
    if (end.choice === "none") return null;
    if (end.choice === "date") return end.date ? { date: end.date } : { problem: `Pick a date for ${name}.` };
    return { rule: end.choice };
  };
  const from = read(draft.from, "from");
  const to = read(draft.to, "to");
  for (const end of [from, to]) if (end && end !== "keep" && "problem" in end) return end;
  if (from === "keep" && to === "keep") return { problem: "Change the from or the to." };
  if (from !== "keep" && to !== "keep") {
    const problem = rangeProblem(from as DateEnd, to as DateEnd);
    if (problem) return { problem };
  }
  return { kind: "date", from: from as EndEdit, to: to as EndEdit };
}

export function ConditionFields({
  draft,
  onChange,
  allowKeep,
}: {
  draft: ConditionDraft;
  onChange: (draft: ConditionDraft) => void;
  allowKeep: boolean;
}) {
  return (
    <>
      <fieldset className="condition-kind">
        <legend className="visually-hidden">Kind of Filter</legend>
        <label className="toggle small">
          <input type="radio" checked={draft.kind === "values"} onChange={() => onChange({ ...draft, kind: "values" })} />
          Values
        </label>
        <label className="toggle small">
          <input type="radio" checked={draft.kind === "date"} onChange={() => onChange({ ...draft, kind: "date" })} />
          Date range
        </label>
      </fieldset>
      {draft.kind === "values" ? (
        <label className="wide">
          Values, separated by commas
          <input value={draft.values} onChange={(e) => onChange({ ...draft, values: e.target.value })} placeholder="Germany, France" />
        </label>
      ) : (
        <>
          <EndPicker label="From" end={draft.from} allowKeep={allowKeep} onChange={(from) => onChange({ ...draft, from })} />
          <EndPicker label="To" end={draft.to} allowKeep={allowKeep} onChange={(to) => onChange({ ...draft, to })} />
        </>
      )}
    </>
  );
}

function EndPicker({
  label,
  end,
  allowKeep,
  onChange,
}: {
  label: string;
  end: EndDraft;
  allowKeep: boolean;
  onChange: (end: EndDraft) => void;
}) {
  return (
    <div className="end-picker">
      <label>
        {label} (inclusive)
        <select value={end.choice} onChange={(e) => onChange({ ...end, choice: e.target.value as EndChoice })}>
          {allowKeep && <option value="keep">Keep as is</option>}
          <option value="none">None (open)</option>
          <option value="date">Fixed date</option>
          <optgroup label="Date Rule, worked out at Export">
            {DATE_RULES.map((r) => (
              <option key={r.rule} value={r.rule}>
                {r.label}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      {end.choice === "date" && (
        <input
          type="date"
          aria-label={`${label} date`}
          value={end.date}
          onChange={(e) => onChange({ ...end, date: e.target.value })}
        />
      )}
    </div>
  );
}
