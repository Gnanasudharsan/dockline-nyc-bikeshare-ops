# infra

Production deployment: one Oracle Cloud Always Free ARM VM running the Compose stack,
HTTPS through either Caddy with free DuckDNS subdomains or a Cloudflare Tunnel
(`COMPOSE_PROFILES`, [ADR 0021](../docs/adr/0021-https-modes.md)), and Vercel for the
website.

| File | Purpose |
| --- | --- |
| `docker-compose.prod.yml` | Production override: localhost-only ports, `restart: always`, VM-sized limits, larger log rotation, the HTTPS front doors (`caddy` + `duckdns`, or `cloudflared`), and the `backup` service |
| `caddy/` | Caddy image with the rate-limit plugin, and the `Caddyfile` (TLS, security headers, `/v1/ask` limit) |
| `duckdns/` | Keeps the DuckDNS subdomains on the VM's IP, with a healthcheck |
| `backup/backup.sh` | Nightly `pg_dump` of the warehouse and Dagster databases with daily/weekly rotation (`BACKUP_ONCE=1` for a single run) |
| `backup/restore.sh` | Restore a dump into a **new** database, wrapped in `timescaledb_pre_restore` / `post_restore` |
| `backup/healthcheck.sh` | Unhealthy if no backup has succeeded in 26 hours |

Guides:

- [Oracle VM](../docs/deploy/oracle-vm.md)
- [DuckDNS and Caddy](../docs/deploy/duckdns-caddy.md)
- [Cloudflare Tunnel](../docs/deploy/cloudflare-tunnel.md)
- [Vercel](../docs/deploy/vercel.md)
- [Operations](../docs/deploy/operations.md)

The **Uptime** workflow (`.github/workflows/uptime.yml`) checks the public API, data
freshness, and the website every 15 minutes.

```bash
make prod-config
```
```bash
make prod-up
```
```bash
make backup-now
```

`tests/test_production_config.py` enforces these rules:
- every published port is bound to `127.0.0.1`, except Caddy's 80 and 443
- the HTTPS front doors are opt-in profiles, and Caddy keeps its certificates
- every long-running service restarts always and has a healthcheck and limits
- every variable used by the override is documented
