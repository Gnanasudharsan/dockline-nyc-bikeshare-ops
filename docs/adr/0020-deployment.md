# 0020. Deployment: one ARM VM, an outbound tunnel, and Vercel

- Status: Accepted
- Date: 2026-11-07

## Context
Everything must run on free tiers, on `linux/arm64`. The warehouse must never be
reachable from the internet. Backups must restore with TimescaleDB intact. The
deployment must be repeatable by one person.

## Decision
- **One Oracle Cloud Always Free Ampere A1 VM** (4 OCPU, 24 GB) runs the whole Compose
  stack with a production override (`infra/docker-compose.prod.yml`). It is the same
  images and configuration as local development, with:
  - every published port bound to `127.0.0.1`
  - `restart: always`
  - memory limits sized for the VM
  - tuned Postgres memory settings
  - larger log rotation
- **Cloudflare Tunnel** publishes `api.<domain>` and `grafana.<domain>` over an
  outbound-only connection. The VM's security list allows only SSH from the owner's IP.
  Cloudflare terminates TLS; WAF rate limiting and Access are optional extra layers.
  Admin UIs (Dagster, Cube, Postgres) are reached over an SSH tunnel.
- **Vercel Hobby** hosts the website (root directory `web`). The site's public
  environment variables point at the tunnel hostnames; the API's CORS allowlist is
  `PROD_WEB_ORIGINS`.
- **Backups:** a `backup` service using the same TimescaleDB image, so `pg_dump` is the
  server's major version.
  - It dumps the warehouse and Dagster databases nightly, keeping 7 daily and 4 weekly.
  - Each dump is written to a temporary name and renamed when complete.
  - A healthcheck fails if no backup has succeeded in 26 hours.
  - Restores always go into a new database, wrapped in `timescaledb_pre_restore` and
    `timescaledb_post_restore`.
  - Verified: an 81 MB dump of 1.49 M raw reports restored in 12 s with the hypertable
    and both continuous aggregates intact.
- **Monitoring:** Grafana alert rules for stale data, failed ingestion and empty
  high-traffic stations, plus a GitHub Actions **Uptime** workflow every 15 minutes. It
  checks API health, data freshness and the website, and a failed run emails the owner.
  Both cost nothing.

## Consequences
- **Single point of failure:** the VM. Recovery means rebuilding the VM from the guide
  and restoring the latest dump, about 30 minutes. Off-site copies of the dumps
  (rclone to free object storage) are documented but optional.
- **No exposed database:** Power BI against production uses an SSH tunnel.
- **Free-tier limits** (Groq tokens, Vercel Hobby, the Oracle idle-reclaim policy) are
  the main operational risks. The uptime workflow catches an idle-reclaimed or stopped
  VM.
