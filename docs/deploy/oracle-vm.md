# Deploy on an Oracle Cloud Always Free ARM VM

Everything runs on one Ampere A1 VM: Oracle's Always Free tier allows 4 OCPU, 24 GB
RAM, and 200 GB of block storage. Nothing is exposed to the internet except SSH:
Cloudflare Tunnel (an outbound connection) publishes the API and Grafana
([cloudflare-tunnel.md](cloudflare-tunnel.md)). The website runs on Vercel
([vercel.md](vercel.md)).

## 1. Create the VM (Oracle console)

1. **Compute → Instances → Create instance.**
2. **Image:** Canonical Ubuntu 24.04 (aarch64).
3. **Shape:** Ampere `VM.Standard.A1.Flex`, 4 OCPU, 24 GB memory.
4. **Networking:** a public subnet with a public IPv4 address, needed for SSH and for
   outbound connections.
5. **SSH keys:** upload your public key.
6. **Boot volume:** 100–200 GB (all within the free 200 GB).
7. **Ingress rules:** in the subnet's security list, allow only **TCP 22 from your own
   IP address**. Delete any other ingress rule. No HTTP or HTTPS port is needed.

## 2. Harden the host

```bash
ssh ubuntu@<vm-ip>
```
```bash
sudo apt-get update && sudo apt-get -y upgrade && sudo apt-get -y install unattended-upgrades ufw git make
```
```bash
sudo ufw default deny incoming && sudo ufw allow OpenSSH && sudo ufw --force enable
```

Oracle's Ubuntu images also ship iptables rules; with `ufw` active and no ingress rules
in the security list, only SSH is reachable.

## 3. Install Docker Engine with the Compose plugin (arm64)

Follow Docker's official instructions for Ubuntu
(<https://docs.docker.com/engine/install/ubuntu/>), then:

```bash
sudo usermod -aG docker ubuntu && newgrp docker
```
```bash
docker compose version
```

Compose 2.24 or newer is required (the production override uses `!override`).

## 4. Get the code and configure it

```bash
git clone https://github.com/Gnanasudharsan/dockline-nyc-bikeshare-ops.git && cd dockline-nyc-bikeshare-ops
```
```bash
make env
```

`make env` generates the internal passwords and secrets. Then edit `.env`:

| Setting | Value |
| --- | --- |
| `POSTGRES_PASSWORD` | a long random value, for example from `openssl rand -hex 24` (the template's `change-me-local-only` is for laptops) |
| `GROQ_API_KEY` (or `GEMINI_API_KEY`) and `LLM_PROVIDER` | your free-tier key |
| `PUBLIC_DOMAIN` | your domain on Cloudflare, for example `example.org` |
| `PROD_WEB_ORIGINS` | the website's URL, for example `https://dockline.vercel.app` |
| `CLOUDFLARE_TUNNEL_TOKEN` | from [cloudflare-tunnel.md](cloudflare-tunnel.md) |
| `CUBESTORE_IMAGE_TAG` | keep the arm64 default (`v1.8.20-arm64v8`) |

`.env` never leaves the VM. It is git-ignored, and `chmod 600 .env` is a good idea.

## 5. Start it

```bash
make prod-config
```
```bash
make prod-up
```
```bash
make prod-ps
```

The first build takes several minutes on the VM. `make prod-ps` should show every
service `healthy`; `migrate` shows `exited (0)`. After about 15 minutes, check the data:

```bash
make check-ingestion
```

Share the public Grafana dashboard once and note the URL it prints; it goes into Vercel's
settings:

```bash
make grafana-public
```

## 6. Access from your laptop

The databases and admin UIs listen only on the VM's `127.0.0.1`. Use an SSH tunnel:

```bash
ssh -N -L 3070:127.0.0.1:3070 -L 4000:127.0.0.1:4000 -L 5433:127.0.0.1:5433 ubuntu@<vm-ip>
```

Dagster is then at <http://localhost:3070>, Cube at <http://localhost:4000>, and Postgres
at `localhost:5433`. Power BI Desktop can point `DbHost` at the laptop's end of the same
tunnel.

## 7. Turn on monitoring

In the GitHub repository, set **Settings → Secrets and variables → Actions → Variables**:

- `PUBLIC_API_URL = https://api.<domain>`
- `PUBLIC_SITE_URL = <website URL>`

The **Uptime** workflow then checks every 15 minutes and emails you when a check fails.
Day-to-day operations: [operations.md](operations.md).
