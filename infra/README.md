# infra

Production deployment: one Oracle Cloud Always Free ARM VM running the Compose stack,
Cloudflare Tunnel for public HTTPS without open ports, and Vercel for the website.

| File | Purpose |
| --- | --- |
| `docker-compose.prod.yml` | Production override: localhost-only ports, `restart: always`, VM-sized limits, larger log rotation, the `cloudflared` tunnel, and the `backup` service |
| `backup/backup.sh` | Nightly `pg_dump` of the warehouse and Dagster databases with daily/weekly rotation (`BACKUP_ONCE=1` for a single run) |
| `backup/restore.sh` | Restore a dump into a **new** database, wrapped in `timescaledb_pre_restore` / `post_restore` |
| `backup/healthcheck.sh` | Unhealthy if no backup has succeeded in 26 hours |

Guides:

- [Oracle VM](../docs/deploy/oracle-vm.md)
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

`tests/test_production_config.py` enforces three rules:
- every published port is bound to `127.0.0.1`
- every long-running service restarts always and has a healthcheck and limits
- every variable used by the override is documented
