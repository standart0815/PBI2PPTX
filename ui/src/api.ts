// Talks to the local server (pbi2pptx/server.py). The per-launch token comes from the
// address the tool opened, and goes with every API call.

import type { EntryJson, ExportProgress, Filter, FilterCheckResult, SelectionJson, TemplateInfo } from "./types";

const token = new URLSearchParams(window.location.search).get("token") ?? "";

export type WindowState = "starting" | "open" | "closed" | "failed";

export interface Status {
  version: string;
  window: { state: WindowState; signed_in: boolean; browser: string; message: string };
}

/** The server can't be reached: the tool was quit. */
export class NotRunning extends Error {}

/** The server refused with a message meant for the User. */
export class Refused extends Error {}

async function call<T>(path: string, method: "GET" | "POST" = "GET", body?: unknown): Promise<T> {
  const isFile = body instanceof File;
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: {
        "X-PBI2PPTX-Token": token,
        ...(body === undefined
          ? {}
          : isFile
            ? { "Content-Type": "application/octet-stream", "X-File-Name": encodeURIComponent(body.name) }
            : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : isFile ? body : JSON.stringify(body),
    });
  } catch {
    throw new NotRunning("PBI2PPTX isn't running");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Refused(data.error ?? `${path}: ${response.status}`);
  return data as T;
}

async function download(path: string): Promise<{ blob: Blob; fileName: string }> {
  let response: Response;
  try {
    response = await fetch(path, { headers: { "X-PBI2PPTX-Token": token } });
  } catch {
    throw new NotRunning("PBI2PPTX isn't running");
  }
  if (!response.ok) throw new Refused((await response.json().catch(() => ({}))).error ?? `${path}: ${response.status}`);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encoded = /filename\*=UTF-8''([^;]+)/.exec(disposition)?.[1];
  return { blob: await response.blob(), fileName: encoded ? decodeURIComponent(encoded) : "Deck.pptx" };
}

export function saveFile(blob: Blob, fileName: string) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 10_000);
}

export const api = {
  status: () => call<Status>("/api/status"),
  showWindow: () => call("/api/window/show", "POST"),
  signOut: () => call("/api/sign-out", "POST"),
  quit: () => call("/api/quit", "POST"),
  addCurrentPage: () => call<{ entry: EntryJson }>("/api/entries/current", "POST"),
  addByAddress: (address: string) => call<{ entry: EntryJson }>("/api/entries/resolve", "POST", { address }),
  openSelection: (content: string) => call<{ selection: SelectionJson }>("/api/selection/open", "POST", { content }),
  getTemplate: () => call<{ template: TemplateInfo | null }>("/api/template"),
  uploadTemplate: (file: File) => call<{ template: TemplateInfo }>("/api/template", "POST", file),
  checkFilter: (pageUrl: string, filter: Filter) => call<FilterCheckResult>("/api/filters/check", "POST", { pageUrl, filter }),
  startExport: (selection: SelectionJson) => call("/api/export", "POST", { selection }),
  exportStatus: () => call<{ export: ExportProgress; deckReady: boolean }>("/api/export"),
  cancelExport: () => call("/api/export/cancel", "POST"),
  downloadDeck: () => download("/api/export/deck"),
  saveSelection: (selection: SelectionJson) =>
    call<{ fileName: string; content: string }>("/api/selection/save", "POST", { selection }),
};
