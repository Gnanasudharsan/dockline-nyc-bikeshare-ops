"use client";

import { useEffect, useState } from "react";
import { API_URL } from "./api";
import { loadLive } from "./liveClient";
import { IS_SNAPSHOT } from "./mode";
import type { Station, StationsResponse } from "./types";

/** Stations with live state, refreshed every 60 s (from /api/live in snapshot mode). */
export function useStations(): { stations: Station[]; asOf: string | null; failed: boolean } {
  const [stations, setStations] = useState<Station[]>([]);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        let body: StationsResponse;
        if (IS_SNAPSHOT) {
          const live = await loadLive();
          body = { as_of: live.kpis.as_of, count: live.stations.length, stations: live.stations };
        } else {
          const response = await fetch(`${API_URL}/v1/stations/live`);
          if (!response.ok) throw new Error(String(response.status));
          body = (await response.json()) as StationsResponse;
        }
        if (!active) return;
        setStations(body.stations);
        setAsOf(body.as_of);
        setFailed(false);
      } catch {
        if (active) setFailed(true);
      }
    };
    void load();
    const timer = setInterval(load, 60_000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return { stations, asOf, failed };
}
