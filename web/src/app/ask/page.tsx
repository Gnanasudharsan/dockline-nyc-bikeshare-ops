import type { Metadata } from "next";
import Link from "next/link";
import { AskPanel } from "@/components/AskPanel";
import { getMetrics, REPO_URL } from "@/lib/api";
import { DEMO_VIDEO_URL, IS_SNAPSHOT } from "@/lib/mode";

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
  if (IS_SNAPSHOT) return <AskUnavailableHere />;
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

/** Snapshot mode: Ask the Data needs Cube and a language model, which run only in the full stack. */
function AskUnavailableHere() {
  return (
    <div className="mx-auto max-w-[900px] px-4 pt-10">
      <h1 className="headline text-3xl">Ask the Data</h1>
      <p className="measure mt-3">
        Ask the Data answers plain-English questions using only Dockline&apos;s certified metrics: a
        language model plans a query, strict validation checks it against an allowlist, and the
        numbers come from the semantic layer. It needs that semantic layer and a language model, so
        it runs in the full self-hosted stack, not in this public snapshot deployment.
      </p>
      <p className="measure mt-4" data-testid="ask-unavailable">
        <a href={`${REPO_URL}#deployment-modes`}>Run the full stack</a> to try it
        {DEMO_VIDEO_URL ? (
          <>
            , or <a href={DEMO_VIDEO_URL}>watch it answer questions</a>
          </>
        ) : null}
        . How it keeps answers grounded:{" "}
        <a href={`${REPO_URL}/blob/main/docs/adr/0018-ask-the-data.md`}>the design decision</a>.
      </p>
      <p className="measure mt-4 text-slate">
        The live numbers are on the <Link href="/">home page</Link>, and the last 24 hours are on
        the <Link href="/live">Live page</Link>.
      </p>
    </div>
  );
}
