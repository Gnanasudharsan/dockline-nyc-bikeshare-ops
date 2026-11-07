"""Runtime configuration, read from environment variables."""

from __future__ import annotations

from pathlib import Path

from psycopg.conninfo import make_conninfo
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting the ingestion service needs. Field names map to UPPER_CASE env vars."""

    model_config = SettingsConfigDict(extra="ignore")

    # Warehouse connection
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_user: str = "dockline"
    postgres_password: SecretStr
    postgres_db: str = "dockline"

    # Sources
    gbfs_discovery_url: str = "https://gbfs.citibikenyc.com/gbfs/gbfs.json"
    gbfs_preferred_version: str = "2.3"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    nyc_latitude: float = 40.7128
    nyc_longitude: float = -74.0060

    # Schedules
    station_information_interval_seconds: int = Field(default=3600, ge=60)
    weather_interval_seconds: int = Field(default=3600, ge=300)
    min_status_poll_seconds: int = Field(default=15, ge=5)
    max_status_poll_seconds: int = Field(default=300, ge=15)

    # HTTP
    http_timeout_seconds: float = Field(default=20.0, gt=0)
    user_agent: str = (
        "dockline-ingestion/0.1 (+https://github.com/Gnanasudharsan/dockline-nyc-bikeshare-ops)"
    )

    # Health
    heartbeat_path: Path = Path("/tmp/dockline-ingestion.heartbeat")  # noqa: S108
    heartbeat_max_age_seconds: int = Field(default=180, ge=30)

    log_level: str = "INFO"

    def conninfo(self) -> str:
        """Return a libpq connection string for the warehouse."""
        return make_conninfo(
            host=self.postgres_host,
            port=str(self.postgres_port),
            user=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            dbname=self.postgres_db,
            application_name="dockline-ingestion",
        )
