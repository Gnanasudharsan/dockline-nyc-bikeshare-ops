import Link from "next/link";
import { LiveHero } from "@/components/LiveHero";
import { getInsights, getLiveKpis } from "@/lib/api";
import { formatInt, formatPercent } from "@/lib/format";

export const revalidate = 10;

export default async function HomePage() {
  const [kpis, insights] = await Promise.all([getLiveKpis(), getInsights()]);
  const concentration = insights?.findings.find((f) => f.id === "rebalancing-concentration");

  const highlights = [
    {
      href: "/live",
      title: "Watch the network move",
      body: "The live dashboard and a 24-hour replay show where stations empty and fill, hour by hour.",
      action: "Open the live view",
    },
    {
      href: "/ask",
      title: "Ask the data in plain English",
      body: "Answers come only from certified metrics, with the definition, the query, and the numbers behind them.",
      action: "Ask a question",
    },
    {
      href: "/insights",
      title: "Where the work is",
      body: concentration?.enough_data
        ? concentration.finding
        : "Findings about empty and full stations, rebalancing, e-bikes, and weather, from live data.",
      action: "Read the insights",
    },
  ];

  return (
    <>
      <LiveHero initial={kpis} />
      <section aria-labelledby="highlights-heading" className="mx-auto mt-16 max-w-[1200px] px-4">
        <h2 id="highlights-heading" className="headline text-xl">
          What Dockline does
        </h2>
        <p className="measure mt-2 text-slate">
          It reads the public station feed about every minute, keeps every report in a time-series
          warehouse, and turns it into certified metrics
          {kpis ? (
            <>
              {" "}
              for <span className="num">{formatInt(kpis.stations)}</span> stations, currently{" "}
              <span className="num">{formatPercent(kpis.fill_ratio)}</span> full on average
            </>
          ) : null}
          .
        </p>
        <div className="mt-8 grid gap-10 md:grid-cols-3 md:gap-8">
          {highlights.map((item) => (
            <article key={item.href} className="border-t-2 border-ink pt-4">
              <h3 className="headline text-lg">{item.title}</h3>
              <p className="mt-2 text-slate">{item.body}</p>
              <p className="mt-3">
                <Link href={item.href} className="font-medium">
                  {item.action}
                </Link>
              </p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
