import type { Metadata } from "next";
import { AskPanel } from "@/components/AskPanel";
import { getMetrics } from "@/lib/api";

export const metadata: Metadata = {
  title: "Ask the Data",
  description:
    "Ask questions about the Citi Bike network in plain English; answers use only certified metrics.",
  alternates: { canonical: "/ask" },
};

export const revalidate = 3600;

const FALLBACK_EXAMPLES = [
  "How many stations have no bikes right now?",
  "Which borough had the lowest availability rate today?",
  "Which stations need the most bikes moved right now?",
];

export default async function AskPage() {
  const catalog = await getMetrics();
  const examples = catalog?.example_questions.slice(0, 6) ?? FALLBACK_EXAMPLES;
  return (
    <div className="mx-auto max-w-[900px] px-4 pt-10">
      <h1 className="headline text-3xl">Ask the Data</h1>
      <p className="measure mt-3 text-slate">
        Ask about bikes, docks, empty and full stations, availability, or rebalancing. A language
        model turns your question into a query over certified metrics only; the numbers come from
        the semantic layer, and every answer shows the definitions and the query behind it.
        Questions it cannot answer from those metrics are declined, with a question it can answer
        instead.
      </p>
      <AskPanel examples={examples} />
    </div>
  );
}
