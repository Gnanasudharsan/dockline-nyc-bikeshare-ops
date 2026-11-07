# Dockline website: design plan

Written before any website code (Phase 6). It turns the "urban wayfinding" system in
`CLAUDE.md` into concrete decisions for each page. Screenshots of the result, and the
critique that followed them, are in `docs/design/screenshots/`.

## 1. Who it is for, and what it must do in 10 seconds

| Visitor | They want to | The site answers with |
| --- | --- | --- |
| Hiring manager / engineer | "Is this real, and is it well built?" | A live map that is moving *now*, real numbers, then How it works (architecture, tests, metrics) |
| Ops-minded reader | "What is happening on the network?" | One live sentence, the KPI strip, the Live page |
| Curious rider | "Where are bikes right now?" | The map and Ask the Data |

The first screen must prove it is live without any explanation. The full-bleed map of
2,500 dots, colored by imbalance, sits under one sentence whose number changes while
you watch. The tone is that of a transit control room: calm and precise, never
salesy.

## 2. Design tokens

**Color** (CSS custom properties on `:root`; dark values under `prefers-color-scheme`
and `[data-theme]`):

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--ink` | `#13202F` | `#E8EDF3` | Primary text |
| `--slate` | `#4A5A6E` | `#9AA8B8` | Secondary text, axes |
| `--paper` | `#F6F7F9` | `#0F1722` | Page background |
| `--surface` | `#FFFFFF` | `#172231` | Raised surfaces (map overlays, cards for real groups) |
| `--line` | `#D9DEE5` | `#263446` | Dividers, only for real groups |
| `--signal` | `#1B5FD1` | `#6A9BFF` | Links, buttons, focus rings, primary series |
| `--starving` | `#E0701F` | `#F08A3E` | No or few bikes |
| `--balanced` | `#A9B3C1` | `#7D8A9C` | Balanced |
| `--flooding` | `#2357C6` | `#5B8DF0` | No or few docks |
| `--offline` | `#7A6F9B` | `#A496CC` | Not in service |

The dark-mode state colors keep their hue and are lightened to at least 3:1 against
`#0F1722`, as required for non-text graphics. Body text meets 4.5:1 in both themes;
`--slate` on `--paper` is about 6.4:1 in light and 7.5:1 in dark.

**Never color alone.**
- Map legend: a state name next to each swatch.
- Map dots: a 1 px outline. Offline dots are hollow rings, so they read as different
  without color.
- Tooltips and table cells: the state name in words.
- Charts: direct labels or a legend with names.

**Type**: Archivo only, loaded with `next/font` and self-hosted, so no layout shift.
- Variable font, including the width axis.
- Headlines semi-condensed (`font-stretch: 87.5%`), weight 650–700.
- Body regular 400, 17 px, line-height 1.55, measure at most 70 characters.
- Scale 1.25: 13.6 / 17 / 21.25 / 26.6 / 33.2 / 41.5 / 51.9 px.
- `font-variant-numeric: tabular-nums` on every live number.
- Sentence case everywhere. No all-caps eyebrows.

**Space**: a 4 px base, using steps of 4, 8, 12, 16, 24, 32, 48, 64 and 96. Hierarchy
comes from spacing, weight and width, not boxes.

**Motion**:
- On first load, stations fade in (opacity 0 → 1 over 600 ms, staggered by borough).
- Live numbers crossfade over 150 ms when they change.
- Nothing else moves.
- With `prefers-reduced-motion`, there is no fade and numbers swap instantly.

## 3. Layout and pages

- **Grid:** a 12-column grid with a 1200 px content width, and 16 px side gutters
  from 360 px up.
- **Header:** the wordmark "Dockline" in semi-condensed bold, with navigation for Live,
  Ask, Insights, How it works and About.
- **Theme:** a light/dark toggle (system by default) whose label states the action
  ("Switch to dark theme").
- **Footer:** the disclaimer, a GitHub link and the data source.

| Page | Purpose | Content |
| --- | --- | --- |
| **Home** | Prove it is live | Full-bleed MapLibre map (OpenFreeMap Positron/Dark tiles) of stations by imbalance. Overlay: the live sentence ("Right now, **142** stations have no bikes to rent."), then a KPI strip over SSE: bikes, docks, empty, full, data age. Below: three highlights linking to Live, Ask and Insights |
| **Live** | Watch and rewind | Public Grafana dashboard embed (lazy, fixed aspect ratio, no layout shift); MapLibre map with a 24-hour replay slider (hourly frames, play/pause, keyboard accessible); legend with counts per state for the frame shown |
| **Ask** | Governed Q&A | One input with example questions as buttons. The answer shows the plain-language answer, the numbers (table), the metrics with definitions, the validated query (collapsible) and data freshness. Refusals show the reason and a suggested question you can ask with one click |
| **Insights** | 4–5 findings | Each finding is a sentence with live numbers, a chart (ECharts, Dockline colors, direct labels) and a recommendation. When there is not enough history, say so plainly instead of showing an empty chart |
| **How it works** | Engineering credibility | Architecture diagram (inline SVG, accessible names); the data path in six steps; metric table (from `/v1/metrics`); tests and quality gates; links to ADRs and the repo |
| **About** | Context | Who built it and why, the disclaimer, data sources and licenses, contact |

## 4. Data and resilience

- The site reads only the Dockline API (`NEXT_PUBLIC_API_URL`); the API reads only Cube.
- Live KPIs come over `EventSource` (`/v1/kpis/stream`), with an initial server-rendered
  value (`/v1/kpis/live`, cached 10 s) so the first paint has numbers.
- Stations: `/v1/stations/live` on the client, refreshed every 60 s.
- Replay: `/v1/stations/replay` (24 hourly frames, compact encoding).
- Insights: `/v1/insights` on the server, revalidated every 15 minutes.
- **Graceful states**:
  - **Loading:** skeletons of the final size.
  - **API down:** "Live data is unavailable right now. The last numbers were from 10:42.
    Retrying every 30 seconds." Static pages still render.
  - **Not enough history:** the "Not enough history yet" text.
  - **Ask errors:** say what happened and what to do next.

## 5. Quality bar and how it is checked

- TypeScript strict, ESLint, Prettier.
- Lighthouse ≥ 90 in all four categories (Performance, Accessibility, Best Practices,
  SEO) on Home and Ask, measured on a production build.
- WCAG 2.2 AA:
  - visible focus (2 px `--signal` ring with offset)
  - target size at least 24 × 24 px
  - skip link and landmarks
  - `aria-live="polite"` on the live sentence, throttled to once per minute for screen
    readers
  - the map has a text alternative: counts by state, plus a link to the table on Live
- No CLS: fixed aspect ratios for the map, embed and charts, fonts via `next/font`, and
  numbers reserved with `tabular-nums` and a minimum width.
- OG and Twitter tags, a generated OG image, `robots.txt` and `sitemap.xml`.
- Playwright screenshots of every page in light/dark × mobile (360 px) and desktop
  (1440 px), saved to `docs/design/screenshots/`, then critiqued and fixed.

## 6. Things to avoid (from the design system)

- ALL-CAPS eyebrows
- gradient washes
- identical shadowed card grids
- fake "01/02/03" numbering
- arrow glyphs on buttons
- cream + terracotta, or black + neon
- marketing superlatives

Buttons say what they do ("Ask", "Play replay", "Show the query"). The site never uses
the Citi Bike logo, name styling or brand colors, and it carries this disclaimer:
"Independent project. Not affiliated with Citi Bike or Lyft. Uses the public GBFS
feed."

## 7. Review log (after the first screenshots)

Screenshots: `docs/design/screenshots/<page>-<theme>-<mobile|desktop>.png`. The site was
built, then critiqued from the screenshots and fixed:

| Found in screenshots | Fix |
| --- | --- |
| Map blank: MapLibre 6's worker never answered under the Next.js bundler | MapLibre 5 (bundled worker) (ADR 0019) |
| Hero card hid lower Manhattan and Brooklyn, the densest stations | The map's visual center is padded to clear the card (≤ 45% of the width, wide screens only) |
| Wordmark and nav links blue instead of ink; links styled only by color | Base styles moved into Tailwind's `@layer base`, so utilities win; links in text are underlined |
| Mobile header wrapped onto three ragged lines | Wordmark and theme on one row; the nav scrolls horizontally |
| Mobile hero panel showed a box edge with no padding | The panel is a box only on wide screens |
| Map sized by `vh` re-rendered when the viewport changed (and broke full-page captures) | Fixed pixel height on phones |
| Chart legends overlapped ("Empty (no bikes" ran into "Full") | ECharts gets the resolved font family; wider legend gap |
| Bar-chart axis and value labels collided at 360 px | Axis labels hidden on narrow bar charts; value labels only when they fit |
| Grafana embed unusable at 360 px | Link to the full-screen dashboard on phones; embed from 640 px |
| A recommendation sent bikes from Hoboken to the Bronx | It now names each borough's own work |
| Lighthouse mobile performance 57 on Home (MapLibre ≈ 1.8 s blocking) | Canvas dot map on phones; interactive map on request |
| Live page 86–89 on desktop (Grafana loaded at start) | Replay first; Grafana inserted only when scrolled into view |
| `/favicon.ico` 404 and an 18 px skip-link target | SVG icon (with an `/favicon.ico` rewrite); 24 px minimum skip link |

## 8. Lighthouse (production build, local stack, Lighthouse 13.6)

| Page | Form factor | Performance | Accessibility | Best practices | SEO | CLS |
| --- | --- | --- | --- | --- | --- | --- |
| / | mobile | 100 | 100 | 100 | 100 | 0 |
| / | desktop | 100 | 100 | 100 | 100 | 0 |
| /live | mobile | 99 | 100 | 100 | 100 | 0.051 |
| /live | desktop | 100 | 100 | 100 | 100 | 0.001 |
| /ask | mobile | 100 | 100 | 100 | 100 | 0 |
| /ask | desktop | 100 | 100 | 100 | 100 | 0 |
| /insights | mobile | 99 | 100 | 100 | 100 | 0 |
| /insights | desktop | 100 | 100 | 100 | 100 | 0 |
| /how-it-works | mobile | 100 | 100 | 100 | 100 | 0 |
| /how-it-works | desktop | 100 | 100 | 100 | 100 | 0 |
| /about | mobile | 100 | 100 | 100 | 100 | 0 |
| /about | desktop | 100 | 100 | 100 | 100 | 0 |

Live on mobile keeps a 0.05 layout shift (rated "good" below 0.1). The legend now reserves
its count text; the remaining shift comes from the replay controls settling after data
loads.
