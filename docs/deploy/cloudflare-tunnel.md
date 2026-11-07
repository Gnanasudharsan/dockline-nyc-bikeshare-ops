# Publish the API and Grafana with Cloudflare Tunnel

The tunnel is an outbound connection from the VM to Cloudflare, so no port on the VM
is open to the internet. Cloudflare provides TLS for `api.<domain>` and
`grafana.<domain>`. Requirements: a free Cloudflare account and a domain whose DNS is
on Cloudflare. No domain? Use [DuckDNS and Caddy](duckdns-caddy.md) instead.

In the VM's `.env`, set `COMPOSE_PROFILES=cloudflare`, `PUBLIC_API_HOST=api.<domain>`
and `PUBLIC_GRAFANA_HOST=grafana.<domain>`.

## 1. Create the tunnel

1. Cloudflare dashboard → **Zero Trust → Networks → Tunnels → Create a tunnel**, and
   choose **Cloudflared**.
2. Name it `dockline`.
3. On the install step, copy the **token**, the long string after `--token`. Put it in
   the VM's `.env` as `CLOUDFLARE_TUNNEL_TOKEN`. Do not run the install command it
   shows; the `cloudflared` container in `infra/docker-compose.prod.yml` uses the token.

## 2. Add public hostnames (routes)

On the tunnel's **Public Hostname** tab:

| Subdomain | Domain | Service |
| --- | --- | --- |
| `api` | your domain | `HTTP` → `api:8000` |
| `grafana` | your domain | `HTTP` → `grafana:3000` |

`api` and `grafana` are Compose service names; the tunnel container reaches them over
the stack's private network.

## 3. Start and verify

On the VM:

```bash
make prod-up
```

Then from anywhere:

```bash
curl https://api.<domain>/health
```

It should return `{"status":"ok","cube":"ok"}`. `https://grafana.<domain>` should show
the Grafana login page.

## 4. Recommended hardening (free)

- **Rate limiting:** Security → WAF → **Rate limiting rules**. Allow, for example, 20
  requests per minute per IP to `api.<domain>/v1/ask`. This is on top of the API's own
  limits.
- **Admin access:** Zero Trust → Access → **Applications**. Protect `grafana.<domain>`
  with an email one-time-pin policy for you, and add a bypass rule for the path
  `/public-dashboards/*` (plus `/public/*` and `/api/public/*`) so the embedded
  dashboard stays public.
- **TLS:** keep **Always Use HTTPS** on (SSL/TLS → Edge Certificates).
