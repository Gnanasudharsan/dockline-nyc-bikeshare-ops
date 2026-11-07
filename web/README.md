# web

The public Dockline website: Next.js (App Router), TypeScript strict, Tailwind CSS 4,
MapLibre GL JS with OpenFreeMap tiles, and Apache ECharts. It reads only the Dockline
API (which reads only Cube) and embeds the public Grafana dashboard. Design rationale:
[`docs/design/design-plan.md`](../docs/design/design-plan.md);
[ADR 0019](../docs/adr/0019-website.md).

| Page | What it shows |
| --- | --- |
| `/` | Full-bleed live map of every station by imbalance, one live sentence, KPI strip over Server-Sent Events, three highlights |
| `/live` | 24-hour replay (hourly frames, play/pause, slider), then the live Grafana dashboard |
| `/ask` | Ask the Data: answer, numbers, metric definitions, the validated query, refusals with a suggested question |
| `/insights` | Five findings recomputed every 15 minutes, each with a chart and a recommendation (or an honest "not enough history yet") |
| `/how-it-works` | Architecture diagram, the data path, the certified metric catalog, quality gates |
| `/about` | Who, why, data sources and licenses |

## Run it

```bash
make up
```
```bash
make web-install
```
```bash
make web-dev
```

The site runs on <http://localhost:3010> (3000 is often taken locally). Settings live in
`web/.env.local`; copy `web/.env.example`. `NEXT_PUBLIC_GRAFANA_PUBLIC_DASHBOARD` is the
token printed by `make grafana-public`. The API's `WEB_ORIGINS` must include the site's
origin.

## Quality

```bash
make web-build
```
```bash
make web-test
```
```bash
make web-screenshots
```

- `make web-build` runs ESLint, TypeScript (strict), Prettier, and a production build.
- `make web-test` runs the Playwright end-to-end tests against a mocked API, with no
  backend needed (CI runs them).
- `make web-screenshots` captures 24 screenshots against the real stack, saved to
  `docs/design/screenshots/`.

Lighthouse results and the screenshot critique are in the design plan.
