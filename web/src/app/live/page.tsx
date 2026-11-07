import type { Metadata } from "next";
import { LazyEmbed } from "@/components/LazyEmbed";
import { ReplayMap } from "@/components/ReplayMap";
import { TrendPanels } from "@/components/TrendPanels";
import { GRAFANA_PUBLIC_DASHBOARD, GRAFANA_URL } from "@/lib/api";
import { IS_SNAPSHOT } from "@/lib/mode";
import { getDailyKpis, getHistory } from "@/lib/snapshot";

export const metadata: Metadata = {
  title: "Live",
  description: "The live Citi Bike network: a 24-hour station replay and network trends.",
  alternates: { canonical: "/live" },
};

// Snapshot history changes every 10 minutes; re-read it at most every 5.
export const revalidate = 300;

export default async function LivePage() {
  if (IS_SNAPSHOT) {
    const [history, daily] = await Promise.all([getHistory(), getDailyKpis()]);
    return (
      <div className="mx-auto max-w-[1200px] px-4 pt-10">
        <h1 className="headline text-3xl">Live network</h1>
        <p className="measure mt-3 text-slate">
          Replay the last 24 hours station by station, then see how the network&apos;s certified
          metrics moved. The history comes from a snapshot of the public feed every 10 minutes.
        </p>
        <ReplayMap />
        <TrendPanels history={history} daily={daily} />
      </div>
    );
  }
  const embed = GRAFANA_PUBLIC_DASHBOARD
    ? `${GRAFANA_URL}/public-dashboards/${GRAFANA_PUBLIC_DASHBOARD}?theme=light&kiosk`
    : null;
  return (
    <div className="mx-auto max-w-[1200px] px-4 pt-10">
      <h1 className="headline text-3xl">Live network</h1>
      <p className="measure mt-3 text-slate">
        Replay the last 24 hours station by station, then watch the operations dashboard, which
        refreshes every 10 seconds from the same certified metrics as the rest of Dockline.
      </p>
      <ReplayMap />
      <section aria-labelledby="dashboard-heading" className="mt-16">
        <h2 id="dashboard-heading" className="headline text-xl">
          Operations dashboard
        </h2>
        {embed ? (
          <p className="mt-4 sm:hidden">
            <a href={embed} rel="noopener">
              Open the live dashboard full screen
            </a>
            <span className="text-slate"> (it needs a wider screen than this one).</span>
          </p>
        ) : null}
        {embed ? (
          <LazyEmbed
            src={embed}
            title="Dockline live operations dashboard (Grafana)"
            className="mt-4 hidden aspect-[16/11] w-full overflow-hidden border border-line bg-surface sm:block lg:aspect-[16/9]"
          />
        ) : (
          <p className="mt-4 border border-line bg-surface p-4 text-slate">
            The embedded dashboard is not configured here. Set{" "}
            <code>NEXT_PUBLIC_GRAFANA_PUBLIC_DASHBOARD</code> to the token from{" "}
            <code>make grafana-public</code>.
          </p>
        )}
      </section>
    </div>
  );
}
