"""Container healthcheck: healthy if station_status succeeded recently.

Exit code 0 = healthy, 1 = unhealthy. Used by the Docker Compose healthcheck.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

DEFAULT_HEARTBEAT = "/tmp/dockline-ingestion.heartbeat"  # noqa: S108


def is_healthy(heartbeat_path: Path, max_age_seconds: float, now: float | None = None) -> bool:
    """Return True if the heartbeat file exists and is younger than ``max_age_seconds``."""
    try:
        modified = heartbeat_path.stat().st_mtime
    except FileNotFoundError:
        return False
    current = time.time() if now is None else now
    return (current - modified) <= max_age_seconds


def main() -> int:
    """Check the heartbeat named by HEARTBEAT_PATH / HEARTBEAT_MAX_AGE_SECONDS."""
    path = Path(os.environ.get("HEARTBEAT_PATH", DEFAULT_HEARTBEAT))
    max_age = float(os.environ.get("HEARTBEAT_MAX_AGE_SECONDS", "180"))
    return 0 if is_healthy(path, max_age) else 1


if __name__ == "__main__":
    sys.exit(main())
