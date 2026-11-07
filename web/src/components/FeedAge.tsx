"use client";

import { formatAge, formatAgo, formatClock, secondsSince } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import type { LiveKpis } from "@/lib/types";

/**
 * Snapshot mode's freshness line, from the feed's own timestamp. On the server and the
 * first client render it shows the clock time; after mount, "N seconds ago", ticking.
 */
export function FeedAge({ kpis }: { kpis: LiveKpis }) {
  const now = useNow(1000);
  const updated = kpis.feed_updated_at ?? kpis.as_of;
  const when = now === null ? `at ${formatClock(updated)}` : formatAgo(secondsSince(updated, now));
  return (
    <>
      Feed updated{" "}
      <span className="num" data-testid="feed-age">
        {when}
      </span>{" "}
      · newest station report {formatAge(kpis.data_freshness_seconds)} old then · refreshes every 30
      s
    </>
  );
}
