// Data flow from the public feed to every surface. Inline SVG with a text alternative.
const NODES = [
  { id: "gbfs", x: 10, y: 20, label: "GBFS feed", sub: "every ~60 s" },
  { id: "meteo", x: 10, y: 120, label: "Open-Meteo", sub: "hourly weather" },
  { id: "ingest", x: 190, y: 70, label: "Ingestion", sub: "Python, validated" },
  { id: "ts", x: 370, y: 70, label: "TimescaleDB", sub: "raw + aggregates" },
  { id: "dbt", x: 370, y: 190, label: "dbt + Dagster", sub: "star schema, tests" },
  { id: "cube", x: 550, y: 70, label: "Cube", sub: "certified metrics" },
  { id: "grafana", x: 730, y: 0, label: "Grafana", sub: "live ops" },
  { id: "api", x: 730, y: 90, label: "API + Ask", sub: "FastAPI, LLM" },
  { id: "pbi", x: 730, y: 180, label: "Power BI", sub: "analysts" },
  { id: "web", x: 910, y: 90, label: "This website", sub: "Next.js" },
] as const;

const EDGES: [string, string][] = [
  ["gbfs", "ingest"],
  ["meteo", "ingest"],
  ["ingest", "ts"],
  ["ts", "dbt"],
  ["ts", "cube"],
  ["cube", "grafana"],
  ["cube", "api"],
  ["ts", "pbi"],
  ["api", "web"],
  ["grafana", "web"],
];

const W = 150;
const H = 56;

export function ArchitectureDiagram() {
  const byId = Object.fromEntries(NODES.map((node) => [node.id, node]));
  return (
    <figure className="mt-6">
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 1070 260"
          role="img"
          aria-labelledby="arch-title arch-desc"
          className="min-w-[760px] text-ink"
        >
          <title id="arch-title">Dockline architecture</title>
          <desc id="arch-desc">
            The GBFS station feed and Open-Meteo weather flow into the ingestion service, which
            writes to TimescaleDB. dbt, scheduled by Dagster, builds the star schema in the same
            warehouse. Cube defines the certified metrics and serves Grafana and the API with Ask
            the Data; Power BI reads a read-only view of the warehouse. The website reads the API
            and embeds Grafana.
          </desc>
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto"
            >
              <path d="M0,0 L10,5 L0,10 z" fill="var(--slate)" />
            </marker>
          </defs>
          {EDGES.map(([from, to]) => {
            const a = byId[from];
            const b = byId[to];
            if (!a || !b) return null;
            const vertical = Math.abs(a.x - b.x) < 10;
            const x1 = vertical ? a.x + W / 2 : a.x + W;
            const y1 = vertical ? a.y + H : a.y + H / 2;
            const x2 = vertical ? b.x + W / 2 : b.x;
            const y2 = vertical ? b.y : b.y + H / 2;
            return (
              <line
                key={`${from}-${to}`}
                x1={x1}
                y1={y1}
                x2={x2 - (vertical ? 0 : 4)}
                y2={y2 - (vertical ? 4 : 0)}
                stroke="var(--slate)"
                strokeWidth={1.4}
                markerEnd="url(#arrow)"
              />
            );
          })}
          {NODES.map((node) => (
            <g key={node.id}>
              <rect
                x={node.x}
                y={node.y}
                width={W}
                height={H}
                rx={4}
                fill="var(--surface)"
                stroke={node.id === "cube" ? "var(--signal)" : "var(--line)"}
                strokeWidth={node.id === "cube" ? 2 : 1}
              />
              <text
                x={node.x + 12}
                y={node.y + 24}
                fontSize={15}
                fontWeight={650}
                fill="currentColor"
              >
                {node.label}
              </text>
              <text x={node.x + 12} y={node.y + 43} fontSize={12.5} fill="var(--slate)">
                {node.sub}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <figcaption className="mt-2 text-sm text-slate">
        Cube (outlined) is the only place metrics are defined; Power BI mirrors its measures by
        name.
      </figcaption>
    </figure>
  );
}
