import type { Metadata } from "next";
import { Chart } from "@/components/Chart";
import { getInsights } from "@/lib/api";
import { formatClock } from "@/lib/format";

export const metadata: Metadata = {
  title: "Insights",
  description: "Findings from the live Citi Bike network, each with the data and a recommendation.",
  alternates: { canonical: "/insights" },
};

export const revalidate = 900;

export default async function InsightsPage() {
  const insights = await getInsights();
  return (
    <div className="mx-auto max-w-[1000px] px-4 pt-10">
      <h1 className="headline text-3xl">Insights</h1>
      <p className="measure mt-3 text-slate">
        Each finding is recomputed from the warehouse every 15 minutes. Where there is not yet
        enough history to say something reliable, the finding says so instead of guessing.
        {insights ? ` Last computed at ${formatClock(insights.as_of)} New York time.` : ""}
      </p>
      {!insights ? (
        <p role="alert" className="mt-10 text-danger">
          Insights are unavailable right now because the data service did not answer. Try again in a
          few minutes.
        </p>
      ) : (
        <div className="mt-12 space-y-20">
          {insights.findings.map((finding) => (
            <section key={finding.id} aria-labelledby={`finding-${finding.id}`}>
              <h2 id={`finding-${finding.id}`} className="headline text-2xl">
                {finding.title}
              </h2>
              <p className="measure mt-3 text-lg">{finding.finding}</p>
              {finding.chart && finding.chart.categories.length > 0 ? (
                <div className="mt-6">
                  <Chart chart={finding.chart} title={`${finding.title}: ${finding.finding}`} />
                </div>
              ) : null}
              <p className="measure mt-4">
                <span className="font-semibold">
                  {finding.enough_data ? "Recommendation: " : "Status: "}
                </span>
                {finding.recommendation}
              </p>
              <p className="mt-2 text-sm text-slate">Based on {finding.basis}.</p>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
