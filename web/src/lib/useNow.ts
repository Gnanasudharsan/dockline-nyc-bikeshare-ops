"use client";

import { useEffect, useState } from "react";

/**
 * The current time, updated every `intervalMs`; null until mounted, so the server
 * render and the first client render agree (no hydration mismatch).
 */
export function useNow(intervalMs: number | null): number | null {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    if (intervalMs === null) return;
    const tick = () => setNow(Date.now());
    tick();
    const timer = setInterval(tick, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}
