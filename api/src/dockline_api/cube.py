"""Minimal async client for Cube's REST API.

Every metric this service returns comes from here. Requests are signed with a
short-lived JWT (HS256, CUBEJS_API_SECRET), which is how Cube authenticates clients.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import jwt


class CubeError(RuntimeError):
    """Cube rejected a query or could not be reached."""


class CubeClient:
    """Run Cube queries (``/load``) and read model metadata (``/meta``)."""

    def __init__(self, http: httpx.AsyncClient, base_url: str, secret: str) -> None:
        """Store the HTTP client, the Cube API base URL, and the signing secret."""
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._secret = secret

    def _token(self) -> str:
        now = int(time.time())
        return jwt.encode({"iat": now, "exp": now + 300}, self._secret, algorithm="HS256")

    async def load(
        self, query: dict[str, Any], *, max_wait_seconds: float = 30.0
    ) -> list[dict[str, Any]]:
        """Run a Cube query and return its rows.

        Cube answers "Continue wait" while a query or pre-aggregation is still being
        built; poll until the result is ready or the deadline passes.
        """
        deadline = time.monotonic() + max_wait_seconds
        while True:
            response = await self._http.post(
                f"{self._base_url}/load",
                json={"query": query},
                headers={"Authorization": self._token()},
            )
            body = response.json()
            if response.status_code == 200 and body.get("error") == "Continue wait":
                if time.monotonic() > deadline:
                    raise CubeError("Cube is still computing this query; try again shortly.")
                await asyncio.sleep(0.5)
                continue
            if response.status_code != 200 or "error" in body:
                raise CubeError(str(body.get("error", f"HTTP {response.status_code}"))[:300])
            rows: list[dict[str, Any]] = body.get("data", [])
            return rows

    async def meta(self) -> dict[str, Any]:
        """Return Cube's model metadata (cubes, measures, dimensions)."""
        response = await self._http.get(
            f"{self._base_url}/meta", headers={"Authorization": self._token()}
        )
        if response.status_code != 200:
            raise CubeError(f"meta: HTTP {response.status_code}")
        result: dict[str, Any] = response.json()
        return result
