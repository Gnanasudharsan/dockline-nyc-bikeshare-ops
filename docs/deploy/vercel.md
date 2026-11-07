# Deploy the website on Vercel (Hobby, free)

1. **vercel.com → Add New → Project** → import `dockline-nyc-bikeshare-ops`.
2. **Root Directory:** `web`. The framework preset is Next.js; keep the default build
   settings.
3. **Environment variables** (Production):

| Name | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://api.<domain>` |
| `NEXT_PUBLIC_GRAFANA_URL` | `https://grafana.<domain>` |
| `NEXT_PUBLIC_GRAFANA_PUBLIC_DASHBOARD` | the token at the end of the URL that `make grafana-public` printed on the VM |
| `NEXT_PUBLIC_SITE_URL` | the site's final URL, for example `https://dockline.vercel.app` |

4. **Deploy.** Then set `PROD_WEB_ORIGINS` on the VM to the same URL and run
   `make prod-up` again, so the API accepts requests from the site (CORS).
5. **Optional custom domain:** add it in Vercel, use it for `NEXT_PUBLIC_SITE_URL` and
   `PROD_WEB_ORIGINS`, and redeploy.

These values are compiled into the site and into its Content Security Policy at build
time, so redeploy after changing any of them. Pull requests get preview deployments
automatically. Previews call the production API, so add their origin to
`PROD_WEB_ORIGINS` only if you need them to work end to end.
