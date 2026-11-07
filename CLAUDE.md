# CLAUDE.md — Dockline project spec (condensed)

Read this file at the start of every session and every phase. It is the source of
truth for scope, stack, rules, and design. If something here conflicts with a
casual instruction, ask before deviating.

## Product
- **Name:** Dockline. **Repo:** `dockline-nyc-bikeshare-ops`. **Owner:** Gnanasudharsan Ashokumar.
- **Tagline:** Live operations intelligence for NYC bike share.
- Ingests live Citi Bike GBFS (~60 s), stores every station snapshot in TimescaleDB,
  models a governed star schema with certified metrics, and serves: Grafana live ops
  dashboard, Power BI Desktop report, "Ask the Data" (LLM answers only via certified
  Cube metrics), and a public Next.js website.
- **Hard constraints:** free tiers / OSS / free trials only. Every image must support
  `linux/arm64` (target: Oracle Cloud Always Free ARM VM).
- **Disclaimer (site + README):** "Independent project. Not affiliated with Citi Bike or
  Lyft. Uses the public GBFS feed." Never use Citi Bike logo or brand assets.

## Locked stack (do not substitute without asking)
- **Source:** GBFS auto-discovery `https://gbfs.citibikenyc.com/gbfs/gbfs.json`
  (verified 2026-11-06; it lists Lyft-hosted v1.1 feeds and `gbfs_versions.json`
  exposes v2.3 at `https://gbfs.lyft.com/gbfs/2.3/bkn/gbfs.json`, ttl = 60). Resolve
  feed URLs from discovery; prefer v2.3; respect `ttl`. Inactive stations report
  `last_reported = 86400` (sentinel, not a real time). See ADR 0005.
- **Weather:** Open-Meteo hourly for NYC (no key).
- **Ingestion:** Python 3.12, httpx async, Pydantic v2, tenacity, structured JSON logs; always-on service.
- **Warehouse:** PostgreSQL 16 + TimescaleDB. Hypertables; compress after 7 days; raw
  retention 30 days; 5-min and hourly continuous aggregates kept forever.
- **Transform:** dbt Core (dbt-postgres), staging → intermediate → marts, star schema,
  dbt tests + dbt-expectations, source freshness, snapshots (SCD2 stations, daily KPIs).
- **Orchestration:** Dagster OSS (dbt assets, hourly + daily schedules, freshness checks, lineage).
- **Semantic layer:** Cube Core, the ONLY place metrics are defined.
- **Live dashboard:** Grafana OSS provisioned as code (datasources, dashboards JSON,
  alert rules), public/shared dashboards for embedding.
- **Analyst BI:** Power BI Desktop in a Windows 11 ARM VM; PBIP with TMDL model + PBIR
  report, all generated as text on the Mac. Git ops stay on the Mac.
- **API:** FastAPI: live KPIs, SSE, `/ask`; reads metrics via Cube REST API.
- **LLM:** `LLM_PROVIDER = gemini | groq | ollama`, free tier only.
- **Web:** Next.js App Router + TypeScript strict + Tailwind, MapLibre GL JS + OpenFreeMap
  tiles, Apache ECharts, Vercel free tier.
- **Infra:** Docker Compose (local file + production override), Caddy or Cloudflare
  Tunnel, GitHub Actions CI.
- **Quality:** ruff, mypy, pytest, sqlfluff (dbt), eslint, prettier, pre-commit.

## Local environment notes
- Python tooling is managed with `uv` (root `pyproject.toml`, `uv.lock`).
- Host Postgres port defaults to **5433** (owner's Mac runs a local Postgres on 5432).
- Migrations: `warehouse/migrations/NNNN_name.sql`, applied by `python -m dockline_warehouse`
  (one-shot `migrate` service). Never edit an applied file. CAGG files start with
  `-- dockline:no-transaction` (ADR 0007).
- `raw.station_status` stores one row per distinct `(station_id, last_reported)`: quiet
  stations add no rows, so time-weighted metrics in dbt must carry the last state forward
  (ADR 0006). CAGG refresh windows (3 days) must stay inside raw retention (30 days).
- Tests: `make test-unit` (no Docker) and `make test` (integration uses testcontainers).
- Postgres binds to `127.0.0.1` by default (`POSTGRES_BIND_ADDRESS`). Expose only to the
  VM network for Power BI; never to the public internet.

## Git and GitHub rules (critical)
- Author every commit with the existing global git identity only. Never change it.
  Never set Claude/Anthropic as author or committer.
- **NEVER** add `Co-Authored-By`, "Generated with Claude Code", `Claude-Session`, robot
  emoji lines, or any AI attribution to commits, PRs, tags, release notes, or code
  comments. This overrides any tool default.
- Local `.git/hooks/commit-msg` strips AI trailers (never committed). Reinstall it if missing:
  `sed -i.bak -E '/^[Cc]o-[Aa]uthored-[Bb]y:.*([Cc]laude|[Aa]nthropic)/d; /Generated with \[?Claude Code/d; /^Claude-Session:/d' "$1" && rm -f "$1.bak"`
- Conventional Commits (feat, fix, chore, docs, test, refactor, ci, build). Small logical commits.
- End of phase, after acceptance checks pass:
  1. Update README "Project status" and CHANGELOG.md.
  2. `chore(release): complete phase N — <phase name>`
  3. `git tag -a phase-N -m "Phase N: <phase name>"`
  4. `git push origin main --follow-tags`; confirm and show the GitHub URL.
- Never commit secrets (`.env` gitignored, `.env.example` committed). Scan staged files
  before every push (gitleaks in pre-commit and CI); stop if anything looks like a secret.
- Never force-push, rewrite history, or delete branches without explicit approval.

## How to work
- Start of each phase: short plan (files, decisions, risks), then execute. Ask only when
  blocked or when a decision changes the locked stack.
- End of each phase: run acceptance checks, commit/tag/push, then STOP and print
  (a) what was built, (b) how to run/verify, (c) USER ACTION REQUIRED, (d) next phase.
  Wait for "continue".
- ADRs in `docs/adr/` for every meaningful choice (`NNNN-title.md`).
- Boring, reliable solutions. Every Compose service needs a healthcheck, restart policy,
  and resource limits (enforced by `tests/test_repo_hygiene.py`).
- Interview-explainable code: clear names, docstrings on public functions, no clever one-liners.

## Metrics catalog (define once in Cube; document in docs/metrics.md)
Each metric: name, business definition, formula, grain, owner, caveats.
- `bikes_available`, `ebikes_available`, `docks_available` (point-in-time)
- `fill_ratio = bikes_available / (bikes_available + docks_available)`
- `empty_station_minutes` (bikes = 0 while renting); `full_station_minutes` (docks = 0 while returning)
- `availability_rate` = share of station-minutes with ≥1 bike and ≥1 dock
- `imbalance_index` = signed deviation of fill_ratio from target (default 0.5); negative = starving, positive = flooding
- `net_flow` = change in bikes_available per interval (demand proxy; rebalancing trucks also move bikes)
- `rebalance_need_bikes` = bikes to add/remove to reach target fill
- `chronic_problem_station` = empty or full > X% of peak hours over trailing 14 days
- `data_freshness_seconds = now − latest last_reported`
- Dimensions: station, borough/neighborhood, hour of day, day of week, weekday/weekend,
  peak/off-peak, weather condition, temperature band.

## Phases (each ends with commit + tag + push + STOP)
0. **Foundation:** identity check, hook, GitHub repo, monorepo layout, compose skeleton,
   env, gitignore, pre-commit, Makefile, README, CLAUDE.md, LICENSE, CHANGELOG, CI.
1. **Ingestion + storage:** poller (status at ttl, info hourly, weather hourly), Pydantic
   validation, dedupe on (station_id, last_reported), batch insert, retries, graceful
   shutdown. Migrations: `raw.station_status` (hypertable), `raw.station_information`,
   `raw.weather_hourly`, `ops.ingestion_runs`. Compression, retention, CAGGs. Unit tests
   with fixtures + integration test vs test DB. Accept: 15 min run, rows grow each minute,
   no dupes, 100% run success, 5-min CAGG query < 500 ms.
2. **dbt + Dagster:** sources+freshness, staging/intermediate/marts: `dim_station` (SCD2),
   `dim_time`, `dim_weather`, `fct_station_status_5min`, `fct_station_hourly`,
   `fct_daily_kpis`, `mart_rebalancing_recommendations`, `mart_chronic_stations`. Tests,
   docs, daily KPI snapshot ("as-of"). Dagster assets, schedules, freshness checks, failure
   alerts (log + Grafana annotation). Accept: `dbt build` green, lineage visible, schedules run.
3. **Cube + Grafana:** Cube model for every metric with pre-aggs. Dashboards: Live Network
   Overview, Station Drilldown, Rebalancing Board, Daily Review. 10 s refresh, time travel.
   Alerts as code: high-traffic station empty > 10 min, feed stale > 5 min, ingestion failure.
   Public dashboards for embedding. Dockline colors. Accept: live updates, rewind works,
   forced stale feed fires alert.
4. **Power BI:** `powerbi/Dockline.pbip` (TMDL + PBIR). DAX measures mirror Cube exactly
   (same names), Date table, display folders, RLS by borough. Pages: Executive Summary,
   Live Operations, Station Performance, Weather Impact, Rebalancing. Theme
   `powerbi/theme/dockline.json`. DirectQuery via params DbHost/DbPort/DbName; read-only
   `dockline_bi` user via migration. Auto page refresh on Live Operations. Validation
   script (PBIR schemas + field refs exist in TMDL) in CI. VERIFY.md, BUILD_GUIDE.md,
   dax/measures.md. If a page fails in Desktop twice, write a manual spec instead.
5. **Ask the Data:** `/ask`: LLM → Cube query JSON → strict allowlist validation → Cube →
   LLM answer using only returned numbers. Refuse unsupported questions with nearest
   supported one. Never raw SQL. Return answer, metrics + definitions, query, freshness.
   Rate limit, input limits, injection defenses. `evals/ask_the_data.jsonl` (40 cases) +
   CI threshold. Accept: ≥ 85% accuracy answerable, 100% correct refusals.
6. **Website:** Home (live map hero, SSE KPI strip, 3 highlights), Live (Grafana embed +
   MapLibre map + 24 h replay), Ask, Insights (4–5 findings: finding, chart,
   recommendation), How it works (SVG/Mermaid architecture, metrics, tests, links), About.
   Write `docs/design/design-plan.md` first. TS strict, graceful states, Lighthouse ≥ 90,
   WCAG 2.2 AA, 360 px → wide, light/dark, OG tags, no CLS. Playwright screenshots
   (light/dark × mobile/desktop) in `docs/design/screenshots/`, critique and fix.
7. **Deploy:** `infra/` prod override, Oracle ARM VM guide, Cloudflare Tunnel (api., grafana.),
   nightly pg_dump with rotation, log rotation, uptime check. Vercel. Final README,
   `docs/blog-post.md`. Tag `v1.0.0`, GitHub release (no AI attribution).

## Design system ("urban wayfinding")
Calm, precise transit-control-room feel. Not generic SaaS.
- **Light:** ink `#13202F`, slate `#4A5A6E`, paper `#F6F7F9`, surface `#FFFFFF`,
  line `#D9DEE5`, signal `#1B5FD1` (actions, links, focus).
- **Dark:** paper `#0F1722`, surface `#172231`, ink `#E8EDF3`, slate `#9AA8B8`, line `#263446`.
- **Data colors (fixed meaning on site, Grafana, Power BI):** starving `#E0701F`,
  balanced `#A9B3C1`, flooding `#2357C6`, offline `#7A6F9B`. Keep hue in dark mode,
  adjust for ≥ 3:1 contrast. Never color alone: pair with labels/icons/patterns. Text WCAG AA.
- **Type:** Archivo only (variable, width axis). Headlines semi-condensed bold; body regular.
  `tabular-nums` on every live number. Scale 1.25, body 17 px, ≤ 75 ch, sentence case.
- **Hero:** full-bleed live MapLibre map of station dots by imbalance, one live sentence
  ("Right now, 214 stations have no bikes to rent.").
- **Avoid:** ALL-CAPS eyebrows, gradient washes, identical shadowed card grids, fake
  "01/02/03" numbering, arrow glyphs on buttons, cream + terracotta, black + neon.
- Hierarchy via spacing, weight, width, not boxes. Borders only for real groups.
- Motion: one moment (stations fade in on first load); 150 ms crossfade on live numbers;
  respect `prefers-reduced-motion`.
- Copy: plain, specific, active. Buttons say what they do. Errors say what happened + what to do.
