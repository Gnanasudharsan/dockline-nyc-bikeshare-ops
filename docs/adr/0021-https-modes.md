# 0021. Two HTTPS modes: Cloudflare Tunnel or Caddy with DuckDNS

- Status: Accepted
- Date: 2026-11-07

## Context
ADR 0020 publishes the API and Grafana through a Cloudflare Tunnel. A tunnel needs a
domain whose DNS is on Cloudflare, and a domain costs money. The project must be
deployable for $0, including by someone without a domain.

## Decision
The production override offers two HTTPS front doors, chosen with
`COMPOSE_PROFILES` in the VM's `.env`. Everything behind them is identical.

| | `cloudflare` | `duckdns` |
| --- | --- | --- |
| Needs | a domain on Cloudflare | a free DuckDNS account |
| Hostnames | `api.<domain>`, `grafana.<domain>` | `<name>-api.duckdns.org`, `<name>-grafana.duckdns.org` |
| Inbound ports | none (outbound tunnel) | 80 and 443 (Caddy only) |
| TLS | Cloudflare | Let's Encrypt, issued and renewed by Caddy |
| `/v1/ask` edge limit | Cloudflare rate-limiting rule (optional) | Caddy `rate_limit`, 10 per minute per IP |
| Services | `cloudflared` | `caddy`, `duckdns` (IP updater) |

- **Caddy** is built with the `caddy-ratelimit` plugin (pinned commit) because the stock
  image has no rate limiter. It adds HSTS, `nosniff`, a referrer policy and a permissions
  policy, hides its server header, denies framing of the API (Grafana must stay
  embeddable), and streams Server-Sent Events without buffering. Certificates live in
  the `caddy_data` volume so restarts do not hit Let's Encrypt's issuance limits.
- **DuckDNS updater:** a 32 MB `curl` container refreshes both subdomains every five
  minutes, so DNS follows the VM if its public IP ever changes.
- **Hostnames are explicit** (`PUBLIC_API_HOST`, `PUBLIC_GRAFANA_HOST`) instead of being
  derived from one domain, because DuckDNS names are siblings, not subdomains of a
  shared parent.
- **Client addresses:** the API trusts `X-Forwarded-For` (`FORWARDED_ALLOW_IPS=*`) so its
  own per-visitor limit sees visitors, not the proxy. This is safe because the API port
  is reachable only from the VM's localhost and the Compose network.
- Cloudflare Tunnel stays the documented choice for anyone with a domain: it opens no
  port and adds Cloudflare's WAF.

## Consequences
- In `duckdns` mode the VM accepts 80 and 443 from the internet. Only Caddy listens
  there; every other port stays on `127.0.0.1`, enforced by
  `tests/test_production_config.py`. The Oracle security list must allow 80/443, which
  is a manual step in the console.
- DuckDNS is a free volunteer service with no SLA. If it is down, existing DNS answers
  usually keep working until their TTL expires; the uptime workflow reports failures.
- Each mode is checked by `docker compose config`, and the Caddy image is validated
  (`caddy validate`) and was exercised against the local stack: HTTPS, headers, SSE, and
  a 429 on the eleventh `/v1/ask` within a minute.
