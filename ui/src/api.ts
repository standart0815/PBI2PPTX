// Talks to the local server (pbi2pptx/server.py). The per-launch token comes from the
// address the tool opened, and goes with every API call.

const token = new URLSearchParams(window.location.search).get("token") ?? "";

export type WindowState = "starting" | "open" | "closed" | "failed";

export interface Status {
  version: string;
  window: { state: WindowState; signed_in: boolean; browser: string; message: string };
}

export class NotRunning extends Error {}

async function call<T>(path: string, method: "GET" | "POST" = "GET"): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { method, headers: { "X-PBI2PPTX-Token": token } });
  } catch {
    throw new NotRunning("PBI2PPTX isn't running");
  }
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return (await response.json()) as T;
}

export const api = {
  status: () => call<Status>("/api/status"),
  showWindow: () => call("/api/window/show", "POST"),
  signOut: () => call("/api/sign-out", "POST"),
  quit: () => call("/api/quit", "POST"),
};
