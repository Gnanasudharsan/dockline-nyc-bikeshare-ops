# Free HTTPS without a domain: DuckDNS and Caddy

Use this mode if you do not own a domain. DuckDNS gives free subdomains, and Caddy
obtains Let's Encrypt certificates for them automatically. If you have a domain on
Cloudflare, [Cloudflare Tunnel](cloudflare-tunnel.md) is the alternative: it opens no
port at all. Why there are two modes: [ADR 0021](../adr/0021-https-modes.md).

## 1. Claim two subdomains

1. Sign in at <https://www.duckdns.org> (GitHub sign-in works).
2. Add two subdomains, for example `dockline-api` and `dockline-grafana`.
3. Set both to the VM's public IP, and copy your token from the top of the page.

## 2. Open ports 80 and 443 to the VM

Caddy needs port 80 for Let's Encrypt's HTTP challenge and 443 for HTTPS. Nothing else
is opened; every other service stays on `127.0.0.1`.

In the Oracle console:
1. **Networking → Virtual cloud networks →** your VCN **→ Subnets →** the VM's subnet
   **→ Security lists →** the default list.
2. **Add ingress rules**, twice: source CIDR `0.0.0.0/0`, IP protocol TCP,
   destination port `80`, then the same for `443`.
3. Keep SSH (22) limited to your own IP.

On the VM, allow them in the host firewall too (Oracle's Ubuntu images reject
everything but SSH by default):

```bash
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
```

## 3. Configure `.env` on the VM

| Setting | Value |
| --- | --- |
| `COMPOSE_PROFILES` | `duckdns` |
| `PUBLIC_API_HOST` | `dockline-api.duckdns.org` |
| `PUBLIC_GRAFANA_HOST` | `dockline-grafana.duckdns.org` |
| `DUCKDNS_DOMAINS` | `dockline-api,dockline-grafana` |
| `DUCKDNS_TOKEN` | your DuckDNS token |
| `PROD_WEB_ORIGINS` | the website's URL, for example `https://dockline.vercel.app` |

Then `make prod-up`. The `caddy` and `duckdns` services start with the rest; Caddy gets
both certificates within a minute of DNS pointing at the VM.

## 4. Check it

```bash
curl https://dockline-api.duckdns.org/health
```

It should return `{"status":"ok","cube":"ok"}`, and
`https://dockline-grafana.duckdns.org` should show the Grafana login page.

What Caddy adds (`infra/caddy/Caddyfile`):
- HTTP to HTTPS redirects, and certificate renewal
- HSTS, `nosniff`, a referrer policy and a permissions policy; no server header
- `X-Frame-Options: DENY` on the API (Grafana stays embeddable for the website)
- at most 10 `/v1/ask` requests per minute per IP, on top of the API's own limits
- unbuffered Server-Sent Events for the live KPI stream

If a certificate does not arrive, read `docker compose logs caddy`. The usual causes are
port 80 still closed in the security list, or DNS not yet pointing at the VM
(`dig +short dockline-api.duckdns.org`).
