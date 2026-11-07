"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { DotMap } from "./DotMap";
import { StateLegend } from "./StateLegend";
import { LiveNumber } from "./LiveNumber";
import { useLiveKpis } from "@/lib/useLiveKpis";
import { useStations } from "@/lib/useStations";
import { useNarrow } from "@/lib/useNarrow";

// MapLibre is large; load it only where it is shown (desktop, or on request on phones).
const StationMap = dynamic(() => import("./StationMap").then((m) => m.StationMap), {
  ssr: false,
  loading: () => (
    <div className="h-[440px] w-full bg-surface md:h-[78vh] md:max-h-[820px] md:min-h-[600px]" />
  ),
});
import { formatAge, formatClock, formatInt } from "@/lib/format";
import { IS_SNAPSHOT } from "@/lib/mode";
import { FeedAge } from "./FeedAge";
import type { LiveKpis } from "@/lib/types";

const KPIS: { key: keyof LiveKpis; label: string }[] = [
  { key: "bikes_available", label: "Bikes available" },
  { key: "docks_available", label: "Free docks" },
  { key: "empty_stations", label: "Empty stations" },
  { key: "full_stations", label: "Full stations" },
];

/**
 * Home hero: the live map with one live sentence and the KPI strip (SSE).
 * Screen readers get the sentence through a polite live region, at most once a minute.
 */
export function LiveHero({ initial }: { initial: LiveKpis | null }) {
  const { kpis, status } = useLiveKpis(initial);
  const { stations, failed } = useStations();
  const [announced, setAnnounced] = useState("");
  const narrow = useNarrow();
  const [interactive, setInteractive] = useState(false);
  const lastAnnounce = useRef(0);

  const sentence = kpis
    ? `Right now, ${formatInt(kpis.empty_stations)} stations have no bikes to rent.`
    : "";
  useEffect(() => {
    if (sentence && Date.now() - lastAnnounce.current > 60_000) {
      lastAnnounce.current = Date.now();
      setAnnounced(sentence);
    }
  }, [sentence]);

  const mapLabel = kpis
    ? `Map of ${formatInt(kpis.stations)} stations: ${formatInt(kpis.starving_stations)} starving, ${formatInt(kpis.balanced_stations)} balanced, ${formatInt(kpis.flooding_stations)} flooding, ${formatInt(kpis.offline_stations)} offline.`
    : "Map of Citi Bike stations by imbalance state.";
  const heroMap =
    narrow && !interactive ? (
      <div className="relative">
        <DotMap
          stations={stations}
          label={mapLabel}
          className="h-[440px] w-full md:h-[78vh] md:max-h-[820px] md:min-h-[600px]"
        />
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
        label={mapLabel}
        className="h-[440px] w-full md:h-[78vh] md:max-h-[820px] md:min-h-[600px]"
        overlayLeft={680}
      />
    );

  return (
    <section aria-labelledby="hero-heading" className="relative">
      {heroMap}
      <div className="mx-auto max-w-[1200px] px-4 md:pointer-events-none md:absolute md:inset-x-0 md:bottom-8">
        <div className="mt-6 md:pointer-events-auto md:mt-0 md:max-w-[620px] md:bg-surface md:p-6 md:shadow-[0_1px_2px_rgba(19,32,47,0.12)]">
          <h1 id="hero-heading" className="headline min-h-[2.3em] text-2xl md:text-3xl">
            {kpis ? (
              <>
                Right now,{" "}
                <LiveNumber value={formatInt(kpis.empty_stations)} className="text-starving" />{" "}
                stations have no bikes to rent.
              </>
            ) : status === "unavailable" ? (
              "Live data is unavailable right now."
            ) : (
              "Loading the live network…"
            )}
          </h1>
          <p aria-live="polite" className="sr-only">
            {announced}
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
            {KPIS.map((item) => (
              <div key={item.key}>
                <dt className="text-sm text-slate">{item.label}</dt>
                <dd className="text-xl font-semibold">
                  <LiveNumber value={kpis ? formatInt(kpis[item.key] as number) : "–"} />
                </dd>
              </div>
            ))}
          </dl>
          <div className="mt-4">
            <StateLegend
              counts={
                kpis
                  ? {
                      starving: kpis.starving_stations,
                      balanced: kpis.balanced_stations,
                      flooding: kpis.flooding_stations,
                      offline: kpis.offline_stations,
                    }
                  : undefined
              }
            />
          </div>
          {IS_SNAPSHOT && kpis && status !== "unavailable" && !failed ? (
            // Not a live region: the age ticks every second and must not be announced.
            <p className="mt-3 text-sm text-slate">
              <FeedAge kpis={kpis} />
            </p>
          ) : null}
          <p
            className={
              IS_SNAPSHOT && kpis && status !== "unavailable" && !failed
                ? "sr-only"
                : "mt-3 text-sm text-slate"
            }
            role="status"
          >
            {status === "unavailable" || failed
              ? `Live data is unavailable right now${kpis ? `; showing numbers from ${formatClock(kpis.as_of)}` : ""}. Retrying automatically.`
              : kpis
                ? IS_SNAPSHOT
                  ? ""
                  : `Updated ${formatClock(kpis.as_of)} · newest station report ${formatAge(kpis.data_freshness_seconds)} old · updates every 10 s`
                : "Connecting to the live feed…"}
          </p>
        </div>
      </div>
    </section>
  );
}
