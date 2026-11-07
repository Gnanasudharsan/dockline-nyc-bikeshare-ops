"use client";

import { useEffect, useState } from "react";
import { API_URL } from "./api";
import type { LiveKpis } from "./types";

export type LiveStatus = "live" | "connecting" | "unavailable";

/**
 * Live network KPIs over Server-Sent Events (/v1/kpis/stream), starting from a
 * server-rendered snapshot so the first paint already has numbers.
 * Falls back to polling every 30 s if the stream cannot be opened.
 */
export function useLiveKpis(initial: LiveKpis | null): {
  kpis: LiveKpis | null;
  status: LiveStatus;
} {
  const [kpis, setKpis] = useState<LiveKpis | null>(initial);
  const [status, setStatus] = useState<LiveStatus>(initial ? "live" : "connecting");

  useEffect(() => {
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
