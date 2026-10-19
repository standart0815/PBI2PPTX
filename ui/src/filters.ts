// Filters as the interface shows and checks them. The page-address rules mirror
// pbi2pptx/page_url.py, so the limits warning here matches the Export's Error Slide.

import type { DateEnd, DateFilter, DateRule, Entry, Filter } from "./types";

export const DATE_RULES: { rule: DateRule; label: string }[] = [
  { rule: "today", label: "Today" },
  { rule: "yesterday", label: "Yesterday" },
  { rule: "startOfThisMonth", label: "Start of this month" },
  { rule: "startOfLastMonth", label: "Start of last month" },
  { rule: "endOfLastMonth", label: "End of last month" },
  { rule: "startOfThisYear", label: "Start of this year" },
  { rule: "startOfLastYear", label: "Start of last year" },
  { rule: "endOfLastYear", label: "End of last year" },
];

/** What an end becomes in an edit: a DateEnd, or "keep" each Filter's own end (multi-edit only). */
export type EndEdit = DateEnd | "keep";

/** The new condition an edit sets: values, or a date range. */
export type Condition = { kind: "values"; values: string[] } | { kind: "date"; from: EndEdit; to: EndEdit };

// Power BI's limits for URL filters (DESIGN.md, Limits).
export const MAX_CONDITIONS = 10;
export const MAX_ADDRESS_LENGTH = 2000;

export function isDateFilter(f: Filter): f is DateFilter {
  return !("values" in f);
}

/** Filters on the same table and column share a key: the Filter Overview groups by it. */
export function fieldKey(f: Filter): string {
  return `${f.table}\u0000${f.column}`;
}

const dateFormat = new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });

/** A fixed date ("2026-10-19") in the browser's format, as the date picker shows it. */
export function formatDate(iso: string): string {
  const day = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(day.getTime()) ? iso : dateFormat.format(day);
}

export function describeEnd(end: DateEnd): string {
  if (end === null) return "";
  if ("rule" in end) return DATE_RULES.find((r) => r.rule === end.rule)?.label ?? end.rule;
  return formatDate(end.date);
}

/** The condition alone: "Germany, France", "01.01.2026 – Today", "from 01.01.2026", "until Today". */
export function describeCondition(f: Filter): string {
  if (!isDateFilter(f)) return f.values.join(", ");
  if (f.from && f.to) return `${describeEnd(f.from)} – ${describeEnd(f.to)}`;
  return f.from ? `from ${describeEnd(f.from)}` : `until ${describeEnd(f.to)}`;
}

export function describeFilter(f: Filter): string {
  return `${f.table} / ${f.column}${isDateFilter(f) ? ": " : " = "}${describeCondition(f)}`;
}

export function sameFilter(a: Filter, b: Filter): boolean {
  const normal = (f: Filter) =>
    isDateFilter(f) ? [f.table, f.column, f.from, f.to] : [f.table, f.column, f.values];
  return JSON.stringify(normal(a)) === JSON.stringify(normal(b));
}

/** Why a from–to with fixed dates can't be, or null. Rules are only known at Export. */
export function rangeProblem(from: DateEnd, to: DateEnd): string | null {
  if (from === null && to === null) return "Choose a from or a to.";
  if (from && to && "date" in from && "date" in to && from.date > to.date) {
    return `From ${formatDate(from.date)} is after to ${formatDate(to.date)}.`;
  }
  return null;
}

// --- Power BI's limits ----------------------------------------------------------------------

// Power BI URL filters encode special characters in table/column names as _xHHHH_.
function escapeName(name: string): string {
  return [...name]
    .map((c) => (/[\p{L}\p{N}_]/u.test(c) ? c : `_x${c.codePointAt(0)!.toString(16).toUpperCase().padStart(4, "0")}_`))
    .join("");
}

function literal(value: string): string {
  return /^-?\d+(\.\d+)?$/.test(value) ? value : `'${value.replaceAll("'", "''")}'`;
}

function conditions(f: Filter): string[] {
  const target = `${escapeName(f.table)}/${escapeName(f.column)}`;
  if (!isDateFilter(f)) {
    return f.values.length === 1
      ? [`${target} eq ${literal(f.values[0])}`]
      : [`${target} in (${f.values.map(literal).join(",")})`];
  }
  // A Date Rule becomes a date of the same length at Export.
  const day = (end: DateEnd) => (end && "date" in end ? end.date : "2000-01-01");
  return [...(f.from ? [`${target} ge ${day(f.from)}`] : []), ...(f.to ? [`${target} lt ${day(f.to)}`] : [])];
}

// Like Python's quote(safe=""): encodeURIComponent leaves !'()* alone, Python doesn't.
function encode(text: string): string {
  return encodeURIComponent(text).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

export function conditionCount(filters: Filter[]): number {
  return filters.reduce((n, f) => n + conditions(f).length, 0);
}

export function pageAddressLength(pageUrl: string, filters: Filter[]): number {
  if (!filters.length) return pageUrl.length;
  const [base, query = ""] = pageUrl.split("?");
  const params = [...new URLSearchParams(query)].map(([k, v]) => `${encode(k)}=${encode(v)}`);
  params.push(`filter=${encode(filters.flatMap(conditions).join(" and "))}`);
  return base.length + 1 + params.join("&").length;
}

/** The interface's warning for an Entry Power BI can't show as asked, or null. */
export function limitWarning(entry: Entry): string | null {
  const count = conditionCount(entry.filters);
  if (count > MAX_CONDITIONS) {
    return `Power BI allows at most ${MAX_CONDITIONS} filter conditions per page; this Entry has ${count} (a Date Filter with from and to counts as two). The Export will make an Error Slide.`;
  }
  const length = pageAddressLength(entry.pageUrl, entry.filters);
  if (length > MAX_ADDRESS_LENGTH) {
    return `The page address with these Filters is ${length.toLocaleString()} characters long; Power BI allows about ${MAX_ADDRESS_LENGTH.toLocaleString()}. The Export will make an Error Slide.`;
  }
  return null;
}

// --- The Filter Overview (DESIGN.md, Filter Overview) ---------------------------------------

/** One Filter of one Entry, addressed by the Entry's id and the Filter's position in it. */
export interface FilterItem {
  ref: string;
  entry: Entry;
  position: number; // of the Entry in the Selection
  filter: Filter;
}

export interface FieldGroup {
  key: string;
  table: string;
  column: string;
  items: FilterItem[];
  entryCount: number;
}

export const filterRef = (entryId: string, index: number) => `${entryId}/${index}`;

/** Every Filter of the Selection, grouped by field, in the order the fields first appear. */
export function groupByField(entries: Entry[]): FieldGroup[] {
  const groups = new Map<string, FieldGroup>();
  entries.forEach((entry, position) =>
    entry.filters.forEach((filter, index) => {
      const key = fieldKey(filter);
      const group = groups.get(key) ?? { key, table: filter.table, column: filter.column, items: [], entryCount: 0 };
      groups.set(key, group);
      group.items.push({ ref: filterRef(entry.id, index), entry, position, filter });
    }),
  );
  for (const group of groups.values()) group.entryCount = new Set(group.items.map((i) => i.entry.id)).size;
  return [...groups.values()];
}

/** Sets the same condition on every selected Filter. With "keep", each Filter keeps its own end.
 *  Refuses as a whole when a result would be impossible, naming the Entries. */
export function editFilters(entries: Entry[], selected: Set<string>, condition: Condition): { entries: Entry[] } | { problem: string } {
  const problems: string[] = [];
  const next = entries.map((entry, position) => {
    if (!entry.filters.some((_, i) => selected.has(filterRef(entry.id, i)))) return entry;
    const filters: Filter[] = [];
    entry.filters.forEach((f, i) => {
      let result: Filter = f;
      if (selected.has(filterRef(entry.id, i))) {
        if (condition.kind === "values") {
          result = { table: f.table, column: f.column, values: condition.values };
        } else {
          const own = isDateFilter(f) ? f : null;
          const from = condition.from === "keep" ? (own?.from ?? null) : condition.from;
          const to = condition.to === "keep" ? (own?.to ?? null) : condition.to;
          const problem = rangeProblem(from, to);
          if (problem) problems.push(`Entry ${position + 1} "${entry.slideTitle}": ${problem}`);
          result = { table: f.table, column: f.column, from, to };
        }
      }
      if (!filters.some((g) => sameFilter(g, result))) filters.push(result); // an edit can make two Filters equal
    });
    return { ...entry, filters };
  });
  if (problems.length) return { problem: `Nothing was changed. ${problems.join(" ")}` };
  return { entries: next };
}

export function removeFilters(entries: Entry[], selected: Set<string>): Entry[] {
  return entries.map((entry) => ({ ...entry, filters: entry.filters.filter((_, i) => !selected.has(filterRef(entry.id, i))) }));
}
