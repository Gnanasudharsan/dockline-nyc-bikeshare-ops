# ingestion

Always-on Python 3.12 service that polls the Citi Bike GBFS feed at its `ttl` (~60 s),
station information hourly, and Open-Meteo weather hourly, validates with Pydantic v2,
and batch-inserts into TimescaleDB. Built in Phase 1.
