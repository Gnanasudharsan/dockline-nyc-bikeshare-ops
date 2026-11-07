# Caddy with the rate-limit plugin (not in the stock image). Multi-arch, runs on arm64.
FROM caddy:2.11.3-builder AS builder
RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit@5625512f24f6f59d6f64fb3aafe5eecff0b286db

FROM caddy:2.11.3
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile
