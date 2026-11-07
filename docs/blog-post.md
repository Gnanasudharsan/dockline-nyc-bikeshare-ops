# How Dockline was built: live bike share operations on free infrastructure

*Draft for publishing. Numbers are from the build and acceptance runs on 2026-11-07.*

A bike share network fails its riders in two quiet ways. A station with no bikes turns
away the person who wanted to start a trip. A station with no free docks strands the
person who wanted to end one. An operations team spends its day moving bikes between
those two kinds of station. Dockline is my attempt to build the data platform such a
team would want, from the public feed to the dashboard, and to build it the way a
production team would: tested, governed, and explainable.

It is an independent project. It is not affiliated with Citi Bike or Lyft, and it uses
only the public GBFS feed.

## The shape of it

About once a minute, Dockline reads the New York network's GBFS feed: roughly 2,500
stations, each reporting bikes, e-bikes, and free docks. A Python service validates
every record and stores each distinct report once, in PostgreSQL with TimescaleDB.

dbt turns those reports into a star schema. Dagster runs it every five minutes, every
hour, and every day.

Cube defines every metric exactly once:
- availability rate
- empty and full station-minutes
- fill ratio
- imbalance
- rebalancing need
- data freshness

Everything that shows a number reads it from there:
- a Grafana operations dashboard
- an API that streams live KPIs to the website
- an "Ask the Data" assistant

A Power BI report mirrors the same metric names, and tests fail if they ever diverge.

The whole system runs on free tiers and open-source software, on ARM: one Oracle Cloud
Always Free VM, a Cloudflare Tunnel so no port is open to the internet, and Vercel for
the website.

## Things the data taught me

**The feed has its own clock.** My first poller fired every 60 seconds. In the first
15-minute acceptance run, two minutes had no new rows. The timer had settled about one
second *before* each feed refresh, so twice it fetched the version it had already seen.
The fix was to schedule each poll from the feed's own `last_updated + ttl`.

The second run then showed the CDN serving a new version 13 to 35 seconds after
`last_updated`, so polls were downloading the full payload almost three times per
version. ETag conditional requests turned most of those into empty `304` responses:
0.95 full downloads per minute instead of 2.7.

**Quiet stations don't report, and that matters for every time-based metric.** The
warehouse stores a row only when a station reports something new. To answer "how many
minutes was this station empty", dbt builds a complete grid of every station and every
five-minute bucket, and carries the last known state forward.

Incremental runs rebuild only the last three hours. I checked that they produce exactly
the same rows as a full rebuild by hashing the table after each.

**Stations sometimes stop talking.** Healthy stations report about every 100 seconds,
and overnight none went more than 30 minutes without a report. So 30 minutes of silence
marks a station offline. Offline minutes are excluded from availability instead of
being counted as empty.

**You don't always need PostGIS.** Boroughs and neighborhoods come from the city's
neighborhood boundaries, simplified and stored as plain Postgres `polygon` values, and
matched with the built-in `@>` operator. A few stations sit on piers just outside every
polygon, and a few New Jersey stations have no region, so there are fallbacks. Every
station gets a place.

## One metric definition, many surfaces

The rule I cared most about: a metric is defined in one place. Grafana has no native
Cube connector, but Cube speaks the Postgres wire protocol. So every Grafana panel is a
`SELECT MEASURE(...)` against Cube, and CI runs every panel's query through Grafana to
prove it still works.

Power BI cannot read Cube directly in this setup, so the Power BI model is generated
from code. Each fact table is named after a cube, and each DAX measure carries the
name of a Cube measure. A test fails if a visible DAX measure has no twin. A separate
check compared Cube's numbers with SQL that follows the DAX formulas exactly; on a
closed time window they matched to six decimal places.

The report itself is plain text (PBIP, TMDL and PBIR), generated on a Mac and
validated in CI against Microsoft's published JSON schemas and Microsoft's own TMDL
parser, so a broken visual or measure fails the build before anyone opens Power BI.

## Letting people ask, without letting the model make things up

"Ask the Data" lets you type a question such as *"Which borough had the lowest
availability rate in the last 7 days?"* The language model never writes SQL. It may
only return a small JSON plan, picking from an allowlisted catalog of metrics,
dimensions, filters, and time ranges.

Code validates that plan strictly:
- unknown keys, members, values, or ranges are rejected
- only then is a Cube query built

A second call writes the answer from the rows Cube returned, and a check rejects any
number in that answer that isn't in those rows. Questions outside the catalog (trips,
revenue, forecasts) are refused, with a suggested question picked from a fixed list.

I measured it with a 40-question evaluation set: 32 answerable questions with expected
plans, and 8 that must be refused, including three injection attempts. The first live
run scored 84.4%, just under my 85% bar. The misses were the model filtering to a
borough *and* grouping by it. Two general rules in the prompt brought it to 96.9%, with
all 8 refusals correct.

The one remaining miss ("How does rain affect availability?" planned as a filter on rain
instead of a comparison across weather) stays in the report as a known miss. CI replays
the recorded run, so the threshold is enforced without an API key, and the recording is
tied to a hash of the prompt so it cannot go stale silently.

## A website that proves it's live

The home page is a full-screen map of every station, colored by imbalance, under one
sentence that updates while you watch: *"Right now, 126 stations have no bikes to
rent."* A replay steps through the last 24 hours. Insights recompute every 15 minutes,
and when there isn't enough history yet they say so instead of drawing conclusions from
a few hours.

I wrote the design plan before any code. Then I reviewed 24 screenshots (light and
dark, phone and desktop) and fixed what they showed:
- a card hiding the densest part of the map
- chart labels colliding at 360 px
- links that were distinguishable only by color
- a recommendation that suggested moving bikes from Hoboken to the Bronx

The hardest one was performance on phones. The map library alone cost about 1.8 seconds
of blocking time on a throttled phone. Phones now draw the same live stations on a
plain canvas and load the interactive map with one tap. Every page now scores 99–100
in Lighthouse's four categories, on mobile and desktop.

## Running it for free, and not exposing it

Production is the same Compose stack with a small override: every port bound to
localhost, `restart: always`, and memory limits sized for the free VM. A Cloudflare
Tunnel publishes only the API and Grafana, over an outbound connection; the VM accepts
SSH and nothing else.

A backup service dumps the databases nightly and rotates them. I tested a restore: an
81 MB dump of 1.49 million raw reports came back in 12 seconds into a fresh database,
with the hypertable and both continuous aggregates intact. Grafana alerts cover a stale
feed, failing ingestion, and empty high-traffic stations, and a scheduled GitHub
workflow checks the public site every 15 minutes.

## What I'd do next

- Add trips data, if a public source allows it, so "demand" stops being a proxy.
- Forecast empty stations an hour ahead from the hourly history.
- Replace static per-borough security roles with user-mapped ones once real users exist.

The code, 20 decision records, and every guide are in the repository.
