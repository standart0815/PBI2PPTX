// The Selection as the interface holds it. The JSON shape matches pbi2pptx/selection.py;
// `id` exists only in the interface, as a stable key for editing and reordering.

/** "Column is one of these values". */
export interface ValueFilter {
  table: string;
  column: string;
  values: string[];
}

/** A named date worked out when the Export starts (pbi2pptx/dates.py). */
export type DateRule =
  | "today"
  | "yesterday"
  | "startOfThisMonth"
  | "startOfLastMonth"
  | "endOfLastMonth"
  | "startOfThisYear"
  | "startOfLastYear"
  | "endOfLastYear";

/** One end of a Date Filter: a fixed date ("2026-10-19"), a Date Rule, or none. */
export type DateEnd = { date: string } | { rule: DateRule } | null;

/** A Filter on a date column, from and/or to, both inclusive. */
export interface DateFilter {
  table: string;
  column: string;
  from: DateEnd;
  to: DateEnd;
}

export type Filter = ValueFilter | DateFilter;

export interface Entry {
  id: string;
  pageUrl: string;
  pageName: string;
  reportName: string;
  slideTitle: string;
  filters: Filter[];
}

export type EntryJson = Omit<Entry, "id">;

export interface Selection {
  name: string;
  renderLanguage: "de-DE" | "en-US";
  slideLayout: string | null;
  showFilters?: boolean; // a Filter Box on slides whose Entry has Filters (absent in older files)
  entries: Entry[];
}

/** Something "Add current page" didn't take over, and why. */
export interface LeftOut {
  what: string;
  reason: string;
}

export type SelectionJson = Omit<Selection, "entries"> & { entries: EntryJson[] };

export const MAX_ENTRIES = 50;

export const emptySelection = (): Selection => ({
  name: "Untitled Selection",
  renderLanguage: "de-DE",
  slideLayout: null,
  showFilters: false,
  entries: [],
});

export function withId(entry: EntryJson): Entry {
  return { ...entry, id: crypto.randomUUID() };
}

export function toJson(selection: Selection): SelectionJson {
  return { ...selection, entries: selection.entries.map(({ id: _id, ...rest }) => rest) };
}

export function reachedThrough(pageUrl: string): string {
  if (pageUrl.includes("/apps/")) return "Power BI App";
  if (pageUrl.includes("/groups/me/")) return "My workspace";
  return "Workspace";
}

// A Template as the server describes it (pbi2pptx/server.py, template_json).
// Rectangles are fractions of the slide (0–1).
export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface LayoutInfo {
  name: string;
  usable: boolean;
  preselected: boolean;
  imageArea: Rect | null;
  title: Rect | null;
  footers: Rect[];
  graphics: (Rect & { name: string })[];
}

export interface TemplateInfo {
  fileName: string;
  slideWidthCm: number;
  slideHeightCm: number;
  templateSlides: number;
  preselected: string | null;
  layouts: LayoutInfo[];
}

// The Export's progress (pbi2pptx/export.py, ExportProgress).
export type EntryState = "waiting" | "capturing" | "captured" | "not verified" | "error slide";

export interface EntryProgress {
  title: string;
  filters: Filter[];
  state: EntryState;
  message: string;
  seconds: number;
}

export interface ExportProgress {
  state: "idle" | "running" | "done" | "cancelled" | "failed";
  entries: EntryProgress[];
  phase: string;
  file_name: string;
  error: string;
}

export interface FilterCheckResult {
  result: "applied" | "not applied" | "not verifiable";
  message: string;
}
