import type { ImbalanceState } from "@/lib/types";
import { formatInt } from "@/lib/format";

export const STATES: { key: ImbalanceState; label: string; meaning: string }[] = [
  { key: "starving", label: "Starving", meaning: "few or no bikes" },
  { key: "balanced", label: "Balanced", meaning: "bikes and docks" },
  { key: "flooding", label: "Flooding", meaning: "few or no docks" },
  { key: "offline", label: "Offline", meaning: "not in service" },
];

/** Swatch + name (+ count) for each state: color is never the only cue. */
export function StateLegend({ counts }: { counts?: Partial<Record<ImbalanceState, number>> }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm" aria-label="Map legend">
      {STATES.map((state) => (
        <li key={state.key} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-block size-3 rounded-full"
            style={
              state.key === "offline"
                ? { border: "2px solid var(--offline)" }
                : { background: `var(--${state.key})`, boxShadow: "0 0 0 1px var(--surface)" }
            }
          />
          <span>
            {state.label}
            <span className="text-slate"> · {state.meaning}</span>
            {/* Always reserve the count so text does not reflow when data arrives. */}
            <span className="num text-slate"> · {formatInt(counts?.[state.key])}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
