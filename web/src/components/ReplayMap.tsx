"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { DotMap } from "./DotMap";
import { StateLegend } from "./StateLegend";
import { API_URL } from "@/lib/api";
import { useStations } from "@/lib/useStations";
import { useNarrow } from "@/lib/useNarrow";

const StationMap = dynamic(() => import("./StationMap").then((m) => m.StationMap), {
  ssr: false,
  loading: () => <div className="mt-4 aspect-[4/3] w-full bg-surface md:aspect-[16/8]" />,
});
import { formatHour } from "@/lib/format";
import type { ImbalanceState, ReplayResponse } from "@/lib/types";

const CODES: Record<string, ImbalanceState> = {
  s: "starving",
  b: "balanced",
  f: "flooding",
  o: "offline",
};

/** The last 24 hours, one frame per hour, with play/pause and a keyboard-friendly slider. */
export function ReplayMap() {
  const { stations } = useStations();
  const [replay, setReplay] = useState<ReplayResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const narrow = useNarrow();
  const [interactive, setInteractive] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/v1/stations/replay`)
      .then((response) =>
        response.ok ? response.json() : Promise.reject(new Error(String(response.status))),
      )
      .then((body: ReplayResponse) => {
        setReplay(body);
        setFrame(Math.max(0, body.hours.length - 1));
      })
      .catch(() => setFailed(true));
  }, []);

  useEffect(() => {
    if (!playing || !replay) return;
    const timer = setInterval(() => {
      setFrame((current) => (current + 1) % replay.hours.length);
    }, 900);
    return () => clearInterval(timer);
  }, [playing, replay]);

  const states = useMemo(() => {
    if (!replay) return undefined;
    const result: Record<string, ImbalanceState | null> = {};
    for (const [id, codes] of Object.entries(replay.stations)) {
      result[id] = CODES[codes[frame] ?? "-"] ?? null;
    }
    return result;
  }, [replay, frame]);

  const counts = useMemo(() => {
    const totals: Record<ImbalanceState, number> = {
      starving: 0,
      balanced: 0,
      flooding: 0,
      offline: 0,
    };
    for (const state of Object.values(states ?? {})) if (state) totals[state] += 1;
    return totals;
  }, [states]);

  // The canvas map takes stations with the frame's state applied (hidden when unknown).
  const frameStations = useMemo(
    () =>
      stations.flatMap((station) => {
        const state = states?.[station.station_id];
        return state ? [{ ...station, imbalance_state: state }] : [];
      }),
    [stations, states],
  );

  const hour = replay?.hours[frame];
  const mapLabel = hour
    ? `Station states at ${formatHour(hour)}: ${counts.starving} starving, ${counts.balanced} balanced, ${counts.flooding} flooding, ${counts.offline} offline.`
    : "Replay map loading.";
  return (
    <section aria-labelledby="replay-heading" className="mt-10">
      <h2 id="replay-heading" className="headline text-xl">
        The last 24 hours, hour by hour
      </h2>
      <p className="measure mt-2 text-slate">
        Each frame shows every station&apos;s state at the end of that hour. Play it to see stations
        empty and fill through the day.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={() => setPlaying((value) => !value)}
          disabled={!replay}
          className="min-h-10 rounded bg-signal px-4 font-medium text-signal-ink disabled:opacity-50"
        >
          {playing ? "Pause replay" : "Play replay"}
        </button>
        <label className="flex min-w-[260px] flex-1 items-center gap-3 text-sm">
          <span className="text-slate">Hour</span>
          <input
            type="range"
            min={0}
            max={Math.max(0, (replay?.hours.length ?? 1) - 1)}
            value={frame}
            onChange={(event) => {
              setPlaying(false);
              setFrame(Number(event.target.value));
            }}
            disabled={!replay}
            aria-valuetext={hour ? formatHour(hour) : "loading"}
            className="w-full accent-[var(--signal)]"
          />
        </label>
        <p className="num min-w-[9ch] font-semibold" aria-live="off">
          {hour ? formatHour(hour) : "–"}
        </p>
      </div>
      <div className="mt-3">
        <StateLegend counts={replay ? counts : undefined} />
      </div>
      {failed ? (
        <p className="mt-4 text-danger" role="alert">
          The replay could not be loaded. Live data may be down; try again in a minute.
        </p>
      ) : (
        <>
          {narrow && !interactive ? (
            <div className="relative mt-4">
              <DotMap stations={frameStations} label={mapLabel} className="aspect-[4/3] w-full" />
              <button
                type="button"
                onClick={() => setInteractive(true)}
                className="absolute bottom-3 right-3 min-h-10 rounded bg-surface px-3 text-sm font-medium text-signal shadow-[0_1px_2px_rgba(19,32,47,0.2)]"
              >
                Open the interactive map
              </button>
            </div>
          ) : (
            <StationMap
              stations={stations}
              states={states}
              label={mapLabel}
              className="mt-4 aspect-[4/3] w-full md:aspect-[16/8]"
            />
          )}
        </>
      )}
      {replay && replay.hours.length < 24 ? (
        <p className="mt-2 text-sm text-slate">
          History so far covers {replay.hours.length} of 24 hours; the replay fills in as data
          accumulates.
        </p>
      ) : null}
    </section>
  );
}
