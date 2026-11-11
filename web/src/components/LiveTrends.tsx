"use client";

import { useEffect, useState } from "react";
import { TrendPanels } from "./TrendPanels";
import type { DailyKpis, History24h } from "@/lib/types";

async function load<T>(name: string): Promise<T | null> {
  try {
    const response = await fetch(`/api/snapshot/${name}`);
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

/** Snapshot mode's trend panels, loaded in the browser from the CDN-cached history. */
export function LiveTrends() {
  const [data, setData] = useState<{ history: History24h | null; daily: DailyKpis | null } | null>(
    null,
  );
  useEffect(() => {
    let active = true;
    void Promise.all([load<History24h>("history-24h"), load<DailyKpis>("daily-kpis")]).then(
      ([history, daily]) => active && setData({ history, daily }),
    );
    return () => {
      active = false;
    };
  }, []);

  if (!data) {
    return (
      <section aria-labelledby="trends-heading" className="mt-16 min-h-[700px]">
        <h2 id="trends-heading" className="headline text-xl">
          Trends
        </h2>
        <p className="mt-4 text-slate">Loading the last 24 hours…</p>
      </section>
    );
  }
  return <TrendPanels history={data.history} daily={data.daily} />;
}
