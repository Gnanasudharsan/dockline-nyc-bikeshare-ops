# Snapshot mode: deploy for $0 with no server

Use this when no always-on server is available. Vercel hosts the site, whose
`/api/live` route computes the certified live metrics from the public feed, and a
GitHub Actions workflow keeps a 24-hour history on the `data` branch. Why and what it
leaves out: [ADR 0022](../adr/0022-snapshot-mode.md).

## 1. Start the history

The **Snapshot** workflow (`.github/workflows/snapshot.yml`) runs every 10 minutes once
it is on `main`. Run it once by hand so the data branch exists:

```bash
gh workflow run snapshot.yml
```

Check the three files:

```bash
curl -s https://raw.githubusercontent.com/<owner>/<repo>/data/latest.json | head -c 300
```

`history-24h.json` and `daily-kpis.json` sit next to it. The history fills in over
24 hours; pages say "not enough history yet" until it has.

## 2. Create the Vercel project

From `web/`, with the Vercel CLI logged in:

```bash
npx vercel@latest link --yes --project dockline
```

In the project's settings, set **Root Directory** to `web` (framework: Next.js) and
connect the GitHub repository (**Settings → Git**). Pushes to `main` then deploy to
production and pull requests get preview URLs. `web/vercel.json` turns deployments
off for the `data` branch, so snapshots never trigger builds.

Environment variables (Production and Preview):

| Name                         | Value                                                                              |
| ---------------------------- | ---------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_DEPLOY_MODE`    | `snapshot`                                                                         |
| `NEXT_PUBLIC_SITE_URL`       | the production URL, for example `https://dockline.vercel.app`                      |
| `NEXT_PUBLIC_DEMO_VIDEO_URL` | optional: a recording of the full stack, linked from the Ask page                  |
| `SNAPSHOT_DATA_URL`          | optional: defaults to this repository's `data` branch on raw.githubusercontent.com |

Deploy:

```bash
npx vercel@latest deploy --prod
```

## 3. Turn on monitoring

Set the repository variables `PUBLIC_SITE_URL` (the production URL) and
`PUBLIC_API_URL` (`<production URL>/api/live`). The **Uptime** workflow then checks
every 15 minutes that the live numbers are under 10 minutes old, that the last
snapshot is under 40 minutes old, and that the site responds. Failed scheduled runs of
either workflow email the repository owner.

## Switching to the full stack later

Bring up the backend ([oracle-vm.md](oracle-vm.md)), then in Vercel set
`NEXT_PUBLIC_DEPLOY_MODE=full` plus the API and Grafana variables from
[vercel.md](vercel.md), and redeploy. The Snapshot workflow can then be disabled.

## Costs and limits

Everything is free: Vercel Hobby (personal, non-commercial use) and GitHub Actions
minutes for public repositories. GitHub may delay scheduled runs at busy times, and it
disables schedules after 60 days without commits to `main`.

## What happened in practice (2026-11-07)

- The CLI created the project from `web/`, but Vercel's Git integration builds from the
  repository root, so the project's **Root Directory** is set to `web` and CLI deploys
  run from the repository root. `.vercelignore` there uploads only `web/` (never the
  local `.env`). The CLI also appends `.env*` to `.gitignore` when linking; that rule
  would hide `.env.example`, so it was reverted.
- `vercel git connect` failed twice with the same generic message. The causes were,
  in turn: the Vercel GitHub app not installed for this repository, and then an
  expired GitHub login connection in Vercel (the API reported GitHub's "Bad
  credentials"). Reconnecting GitHub under Vercel **Account Settings →
  Authentication** fixed it. `vercel api "/v1/integrations/search-repo?query=<name>"`
  shows the real error.
- GitHub's scheduler took more than 20 minutes to start a new `*/10` schedule; manual
  runs (`gh workflow run snapshot.yml`) filled the gap.
- Production: <https://dockline-nyc.vercel.app> (an extra `*.vercel.app` domain on the
  project). Lighthouse 13.6 against production:

| Page | Form factor | Performance | Accessibility | Best practices | SEO | CLS |
| --- | --- | --- | --- | --- | --- | --- |
| / | mobile | 99 | 100 | 100 | 100 | 0 |
| / | desktop | 100 | 100 | 100 | 100 | 0 |
| /live | mobile | 100 | 100 | 100 | 100 | 0 |
| /live | desktop | 100 | 100 | 100 | 100 | 0.001 |

Playwright against production (desktop and mobile, light and dark): the map renders
with live numbers, the feed age ticks and stays under 3 minutes, the replay slider and
play button work, the Ask page shows its note, no console errors, no horizontal
scrolling.
