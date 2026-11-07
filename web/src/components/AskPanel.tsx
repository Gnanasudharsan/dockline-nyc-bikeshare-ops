"use client";

import { useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import { formatAge } from "@/lib/format";
import type { AskResponse } from "@/lib/types";

const MAX_CHARS = 300;

function formatCell(key: string, value: unknown): string {
  if (typeof value === "number") {
    const isRatio = /rate|share|ratio/.test(key) && value <= 1 && value >= -1;
    return isRatio
      ? `${(value * 100).toFixed(1)}%`
      : value.toLocaleString("en-US", { maximumFractionDigits: 1 });
  }
  return value === null || value === undefined ? "–" : String(value);
}

/** Ask the Data: question box, example questions, and a transparent answer. */
export function AskPanel({ examples }: { examples: string[] }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    setQuestion(trimmed);
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/v1/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      const body = (await response.json()) as AskResponse | { detail: string };
      if (!response.ok) {
        setResult(null);
        setError(
          "detail" in body
            ? body.detail
            : `The question could not be answered (HTTP ${response.status}).`,
        );
      } else {
        setResult(body as AskResponse);
      }
    } catch {
      setResult(null);
      setError("Dockline could not be reached. Check your connection and try again in a minute.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void ask(question);
        }}
        className="mt-6"
      >
        <label htmlFor="question" className="font-medium">
          Your question
        </label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-start">
          <textarea
            id="question"
            ref={input}
            value={question}
            onChange={(event) => setQuestion(event.target.value.slice(0, MAX_CHARS))}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void ask(question);
              }
            }}
            rows={2}
            maxLength={MAX_CHARS}
            placeholder="Which borough has the most empty stations right now?"
            aria-describedby="question-help"
            className="min-h-14 flex-1 resize-y border border-line bg-surface p-3 text-ink placeholder:text-slate"
          />
          <button
            type="submit"
            disabled={pending || !question.trim()}
            className="min-h-12 rounded bg-signal px-5 font-medium text-signal-ink disabled:opacity-50"
          >
            {pending ? "Asking…" : "Ask"}
          </button>
        </div>
        <p id="question-help" className="mt-1 text-sm text-slate">
          <span className="num">{question.length}</span>/{MAX_CHARS} characters · answers use only
          certified metrics; up to 6 questions a minute.
        </p>
      </form>

      <div className="mt-6">
        <p className="text-sm text-slate">Try one of these:</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {examples.map((example) => (
            <li key={example}>
              <button
                type="button"
                onClick={() => void ask(example)}
                disabled={pending}
                className="min-h-9 rounded border border-line bg-surface px-3 text-left text-sm hover:border-signal disabled:opacity-50"
              >
                {example}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div aria-live="polite" className="mt-10">
        {error ? (
          <p role="alert" className="text-danger">
            {error}
          </p>
        ) : null}
        {result ? (
          <article aria-label="Answer" className="border-t-2 border-ink pt-4">
            <p className="text-sm text-slate">{result.question}</p>
            <p className="headline mt-2 text-xl">{result.answer}</p>
            {result.status === "refused" && result.suggestion ? (
              <p className="mt-3">
                <button
                  type="button"
                  onClick={() => void ask(result.suggestion ?? "")}
                  className="min-h-9 font-medium text-signal underline underline-offset-4"
                >
                  Ask instead: {result.suggestion}
                </button>
              </p>
            ) : null}
            {result.status === "answered" ? (
              <>
                <p className="mt-2 text-sm text-slate">
                  Data age {formatAge(result.data_freshness_seconds)} · answered in{" "}
                  {(result.elapsed_ms / 1000).toFixed(1)} s
                  {result.answer_source === "template"
                    ? " · plain summary (the model's wording did not match the numbers)"
                    : ""}
                </p>
                {result.rows.length > 0 ? (
                  <div className="mt-6 overflow-x-auto">
                    <table className="w-full min-w-[320px] text-left text-sm">
                      <caption className="sr-only">Numbers behind the answer</caption>
                      <thead>
                        <tr className="border-b border-line">
                          {Object.keys(result.rows[0] ?? {}).map((key) => (
                            <th key={key} scope="col" className="py-2 pr-4 font-medium">
                              {key.replaceAll("_", " ")}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.rows.slice(0, 20).map((row, index) => (
                          <tr key={index} className="border-b border-line">
                            {Object.entries(row).map(([key, value]) => (
                              <td key={key} className="num py-2 pr-4">
                                {formatCell(key, value)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <h2 className="headline mt-8 text-lg">Metrics used</h2>
                <dl className="mt-2 space-y-2">
                  {result.metrics.map((metric) => (
                    <div key={metric.name}>
                      <dt className="font-medium">
                        <code>{metric.name}</code>
                      </dt>
                      <dd className="measure text-slate">{metric.definition}</dd>
                    </div>
                  ))}
                </dl>
                <details className="mt-6">
                  <summary className="min-h-9 cursor-pointer font-medium text-signal">
                    Show the query
                  </summary>
                  <pre className="mt-2 overflow-x-auto border border-line bg-surface p-3 text-sm">
                    {JSON.stringify(result.query, null, 2)}
                  </pre>
                </details>
              </>
            ) : null}
          </article>
        ) : null}
      </div>
    </div>
  );
}
