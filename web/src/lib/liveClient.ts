"use client";

import type { LiveResponse } from "./types";

// Snapshot mode: the KPI strip and the map both read /api/live. Share one request
// between them, and reuse a response for a few seconds.
const REUSE_MS = 10_000;
let last: { at: number; data: LiveResponse } | null = null;
let inflight: Promise<LiveResponse> | null = null;

export function loadLive(): Promise<LiveResponse> {
  if (last && Date.now() - last.at < REUSE_MS) return Promise.resolve(last.data);
  inflight ??= fetch("/api/live")
    .then((response) =>
      response.ok ? response.json() : Promise.reject(new Error(String(response.status))),
    )
    .then((data: LiveResponse) => {
      last = { at: Date.now(), data };
      return data;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}
