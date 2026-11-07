"use client";

import { useEffect, useState } from "react";
import { API_URL } from "./api";
import { loadLive } from "./liveClient";
import { IS_SNAPSHOT } from "./mode";
import type { LiveKpis } from "./types";

/** Snapshot mode refreshes from /api/live (cached ~30 s on the CDN). */
const SNAPSHOT_POLL_MS = 30_000;

export type LiveStatus = "live" | "connecting" | "unavailable";

/**
 * Live network KPIs over Server-Sent Events (/v1/kpis/stream), starting from a
 * server-rendered snapshot so the first paint already has numbers.
 * Falls back to polling every 30 s if the stream cannot be opened.
 * In snapshot mode there is no stream: it polls /api/live every 30 s.
 */
export function useLiveKpis(initial: LiveKpis | null): {
  kpis: LiveKpis | null;
  status: LiveStatus;
} {
  const [kpis, setKpis] = useState<LiveKpis | null>(initial);
  const [status, setStatus] = useState<LiveStatus>(initial ? "live" : "connecting");

  useEffect(() => {
    if (!IS_SNAPSHOT) return;
    let active = true;
    const load = () =>
      loadLive()
        .then((live) => {
          if (!active) return;
          setKpis(live.kpis);
          setStatus("live");
        })
        .catch(() => active && setStatus("unavailable"));
    void load();
    const timer = setInterval(load, SNAPSHOT_POLL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (IS_SNAPSHOT) return;
    let closed = false;
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    const source = new EventSource(`${API_URL}/v1/kpis/stream`);

    source.addEventListener("kpis", (event) => {
      setKpis(JSON.parse((event as MessageEvent<string>).data) as LiveKpis);
      setStatus("live");
    });
    source.addEventListener("unavailable", () => setStatus("unavailable"));
    source.onerror = () => {
      if (closed) return;
      setStatus("unavailable");
      source.close();
      pollTimer ??= setInterval(async () => {
        try {
          const response = await fetch(`${API_URL}/v1/kpis/live`);
          if (response.ok) {
            setKpis((await response.json()) as LiveKpis);
            setStatus("live");
          }
        } catch {
          setStatus("unavailable");
        }
      }, 30_000);
    };

    return () => {
      closed = true;
      source.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, []);

  return { kpis, status };
}
