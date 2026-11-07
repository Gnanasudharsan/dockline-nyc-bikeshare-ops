# 0019. The website: static pages, live islands, and a map that respects phones

- Status: Accepted
- Date: 2026-11-07

## Context
The site must prove the platform is live within seconds, meet Lighthouse ≥ 90 and WCAG
2.2 AA, work from 360 px wide, and have no layout shift. Its data comes only from the
Dockline API.

## Decision
- **Pages are static, with timed refresh** (Next.js App Router):
  - Home every 10 s, Insights every 15 minutes, Ask and How it works hourly.
  - The server fetches return `null` when the API is down, so each page renders a plain
    "unavailable" state instead of failing.
- **Live parts are small client components**, so the rest of each page stays static:
  - KPIs over Server-Sent Events, with a server-rendered first value and polling as a
    fallback.
  - Stations refreshed every 60 s.
  - The replay.
  - Ask.
- **Maps:**
  - **Library:** MapLibre GL JS 5 with OpenFreeMap vector tiles (Positron light, Dark
    dark). MapLibre 6's separately loaded web worker did not complete its handshake
    under the Next.js bundler; 5.x bundles its worker and works, so 5.x is pinned.
  - **Phones:** loading MapLibre cost about 1.8 s of main-thread blocking on a throttled
    phone (Lighthouse performance 57). Below 640 px, the hero and the replay draw the
    same live stations on a plain canvas, with no basemap and no library. "Open the
    interactive map" loads MapLibre on request. Desktop keeps the full map.
  - **Colors:** state colors and token values come from CSS variables, so both themes
    use the same palette. Offline stations are rings, so state never relies on color
    alone.
- **The Grafana embed loads only when it scrolls into view** (IntersectionObserver).
  Native iframe lazy loading starts too early and pulled in about 1 MB of third-party
  JavaScript. On phones the page links to the full-screen dashboard instead.
- **Security headers:**
  - a strict Content Security Policy, allowing only the site itself, the API,
    OpenFreeMap, and the Grafana frame
  - `frame-ancestors 'none'`
  - `nosniff`
  - a strict referrer policy
- **Testing:**
  - Playwright end-to-end tests against a mocked API run in CI.
  - A screenshot suite (6 pages × light/dark × 360/1440 px) runs against the real stack
    for design review.

## Consequences
- **Lighthouse:** 99–100 in every category on every page, mobile and desktop.
- **Layout shift:** 0 everywhere except Live on mobile (0.05, within "good").
- **Phone map:** phones see a dot map without streets until they ask for the
  interactive one. This is a deliberate trade for speed, and the button says so.
