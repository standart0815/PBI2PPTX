// The Selection as the interface holds it. The JSON shape matches pbi2pptx/selection.py;
// `id` exists only in the interface, as a stable key for editing and reordering.

export interface Filter {
  table: string;
  column: string;
  values: string[];
}

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
  entries: Entry[];
}

export type SelectionJson = Omit<Selection, "entries"> & { entries: EntryJson[] };

export const MAX_ENTRIES = 50;

export const emptySelection = (): Selection => ({
  name: "Untitled Selection",
  renderLanguage: "de-DE",
  slideLayout: null,
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

export function describeFilter(f: Filter): string {
  return `${f.table} / ${f.column} = ${f.values.join(", ")}`;
}

export function sameFilter(a: Filter, b: Filter): boolean {
  return a.table === b.table && a.column === b.column && a.values.join("\u0000") === b.values.join("\u0000");
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
