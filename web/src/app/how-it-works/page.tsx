import type { Metadata } from "next";
import { ArchitectureDiagram } from "@/components/ArchitectureDiagram";
import { getMetrics, REPO_URL } from "@/lib/api";
import { DEPLOY_MODE, IS_SNAPSHOT } from "@/lib/mode";

export const metadata: Metadata = {
  title: "How it works",
  description: "Architecture, metrics, and quality gates behind Dockline.",
  alternates: { canonical: "/how-it-works" },
};

export const revalidate = 3600;

const STEPS = [
  {
    title: "Ingest",
    body: "A Python service polls the public GBFS feed on the feed's own clock (about every minute) with conditional requests, validates every station record, and stores each distinct report once. Weather comes from Open-Meteo hourly.",
  },
  {
    title: "Store",
    body: "PostgreSQL with TimescaleDB keeps raw reports for 30 days (compressed after 7) and 5-minute and hourly continuous aggregates forever.",
  },
  {
    title: "Model",
    body: "dbt builds a star schema: a carried-forward 5-minute grid of every station, hourly and daily facts, a station history (SCD2), and live rebalancing and chronic-station marts, with more than 130 tests. Dagster schedules it every 5 minutes, hourly, and daily.",
  },
  {
    title: "Define",
    body: "Cube is the single semantic layer: every metric is defined once there, with pre-aggregations for speed. Grafana, the API, and this site read numbers only from Cube.",
  },
  {
    title: "Serve",
    body: "Grafana shows live operations with alerts as code; Power BI gives analysts a DirectQuery model whose DAX measures carry the same names; the API streams live KPIs and answers questions.",
  },
  {
    title: "Ask",
    body: "A language model only plans a query from an allowlisted catalog. Code validates it, Cube answers it, and the written answer may only contain numbers Cube returned.",
  },
];

// The point-in-time metrics snapshot mode serves (wording from docs/metrics.md); the
// full catalog comes from the API when the full stack is running.
const SNAPSHOT_MEASURES = [
  ["bikes_available", "Bikes a rider could rent right now (in-service stations, includes e-bikes)"],
  ["ebikes_available", "E-bikes a rider could rent right now"],
  ["docks_available", "Empty docks a rider could return to right now"],
  ["fill_ratio", "bikes_available / (bikes_available + docks_available) over in-service stations"],
  [
    "imbalance_state",
    "Offline if not in service; starving if no bikes or fill ≤ 20%; flooding if no docks or fill ≥ 80%; else balanced",
  ],
  ["empty_stations / full_stations", "In-service stations with no bike / no free dock"],
  [
    "rebalance_need_bikes",
    "Bikes to add or remove to bring every starving or flooding station to half full",
  ],
  [
    "availability_rate",
    "Share of in-service station samples with at least one bike and one dock (10-minute samples here)",
  ],
  ["data_freshness_seconds", "Seconds since the newest station report"],
].map(([name, definition]) => ({ name, definition, topic: "Snapshot mode", unit: "" }));

const MODES = [
  {
    name: "Full stack",
    id: "full",
    body: "The whole platform on one free Oracle Cloud ARM server: ingestion every minute, TimescaleDB, dbt and Dagster, Cube, Grafana with alerts, the Power BI model, the API, and Ask the Data. Every report is kept, and every metric is defined once in Cube.",
  },
  {
    name: "Snapshot mode",
    id: "snapshot",
    body: "Only free hosting with no server: this site's /api/live route computes the certified point-in-time metrics straight from the public feed, and a GitHub Actions workflow saves a snapshot every 10 minutes for the 24-hour replay and trends. No warehouse, Grafana, or Ask the Data. A test runs both implementations on the same recorded feed and requires identical results.",
  },
];

const GATES = [
  "Ruff, strict mypy, ESLint, TypeScript strict, SQLFluff, Prettier",
  "Unit tests plus integration tests against a throwaway TimescaleDB",
  "dbt data tests and unit tests (dbt-expectations, dbt-utils)",
  "Every Grafana panel query executed through Cube in CI",
  "Power BI files validated against Microsoft's schemas and parser",
  "Ask the Data evaluation: 40 cases, at least 85% correct and 100% correct refusals",
  "Secret scanning on every commit and the full history",
];

export default async function HowItWorksPage() {
  const catalog = IS_SNAPSHOT ? null : await getMetrics();
  const measures = IS_SNAPSHOT
    ? SNAPSHOT_MEASURES
    : catalog?.topics.flatMap((topic) =>
        topic.measures.map((measure) => ({ ...measure, topic: topic.name })),
      );
  return (
    <div className="mx-auto max-w-[1100px] px-4 pt-10">
      <h1 className="headline text-3xl">How it works</h1>
      <p className="measure mt-3 text-slate">
        Dockline is a small, production-style data platform built from free and open-source parts,
        designed to run on a single ARM server. Every design decision is recorded in an{" "}
        <a href={`${REPO_URL}/tree/main/docs/adr`}>architecture decision record</a>.
      </p>

      <section aria-labelledby="architecture" className="mt-12">
        <h2 id="architecture" className="headline text-2xl">
          Architecture
        </h2>
        <ArchitectureDiagram />
      </section>

      <section aria-labelledby="path" className="mt-16">
        <h2 id="path" className="headline text-2xl">
          From feed to answer
        </h2>
        <ol className="mt-6 grid gap-x-10 gap-y-8 md:grid-cols-2">
          {STEPS.map((step) => (
            <li key={step.title}>
              <h3 className="headline text-lg">{step.title}</h3>
              <p className="measure mt-1 text-slate">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="deployment-modes" className="mt-16">
        <h2 id="deployment-modes" className="headline text-2xl">
          Deployment modes
        </h2>
        <p className="measure mt-2 text-slate">
          The same code deploys two ways, chosen by one setting. This site runs in{" "}
          <strong className="text-ink">{IS_SNAPSHOT ? "snapshot mode" : "the full stack"}</strong>
          {IS_SNAPSHOT
            ? ", because a free always-on server was not available; switching back is a change of one environment variable."
            : "."}
        </p>
        <dl className="mt-6 grid gap-x-10 gap-y-8 md:grid-cols-2">
          {MODES.map((mode) => (
            <div
              key={mode.id}
              className={mode.id === DEPLOY_MODE ? "border-l-2 border-signal pl-4" : "pl-[18px]"}
            >
              <dt className="headline text-lg">
                {mode.name}
                {mode.id === DEPLOY_MODE ? (
                  <span className="text-sm font-normal text-slate"> · this site</span>
                ) : null}
              </dt>
              <dd className="measure mt-1 text-slate">{mode.body}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-sm">
          <a href={`${REPO_URL}/blob/main/docs/adr/0022-snapshot-mode.md`}>Why two modes</a>
        </p>
      </section>

      <section aria-labelledby="metrics" className="mt-16">
        <h2 id="metrics" className="headline text-2xl">
          Certified metrics
        </h2>
        <p className="measure mt-2 text-slate">
          Defined once in the semantic layer; the full catalog with formulas and caveats is in{" "}
          <a href={`${REPO_URL}/blob/main/docs/metrics.md`}>docs/metrics.md</a>.
        </p>
        {measures ? (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <caption className="sr-only">
                {IS_SNAPSHOT
                  ? "Metrics served in snapshot mode"
                  : "Metrics available to Ask the Data"}
              </caption>
              <thead>
                <tr className="border-b border-line">
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Metric
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Data
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    Definition
                  </th>
                </tr>
              </thead>
              <tbody>
                {measures.map((measure) => (
                  <tr
                    key={`${measure.topic}-${measure.name}`}
                    className="border-b border-line align-top"
                  >
                    <td className="py-2 pr-4">
                      <code>{measure.name}</code>
                    </td>
                    <td className="py-2 pr-4 text-slate">{measure.topic}</td>
                    <td className="py-2">{measure.definition}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-slate">The metric catalog is unavailable right now.</p>
        )}
      </section>

      <section aria-labelledby="quality" className="mt-16">
        <h2 id="quality" className="headline text-2xl">
          Quality gates
        </h2>
        <ul className="measure mt-4 list-disc space-y-1 pl-5">
          {GATES.map((gate) => (
            <li key={gate}>{gate}</li>
          ))}
        </ul>
        <p className="mt-6">
          <a href={REPO_URL}>Read the source on GitHub</a>
        </p>
      </section>
    </div>
  );
}
