import type { Metadata } from "next";
import { ArchitectureDiagram } from "@/components/ArchitectureDiagram";
import { getMetrics, REPO_URL } from "@/lib/api";

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
  const catalog = await getMetrics();
  const measures = catalog?.topics.flatMap((topic) =>
    topic.measures.map((measure) => ({ ...measure, topic: topic.name })),
  );
  return (
    <div className="mx-auto max-w-[1100px] px-4 pt-10">
      <h1 className="headline text-3xl">How it works</h1>
      <p className="measure mt-3 text-slate">
        Dockline is a small, production-style data platform built from free and open-source parts,
        running on a single ARM server. Every design decision is recorded in an{" "}
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
              <caption className="sr-only">Metrics available to Ask the Data</caption>
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
