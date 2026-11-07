"""LLM providers (free tiers only): Groq, Gemini, or a local Ollama.

Each provider takes a system prompt and a user message and returns a JSON object. The
caller validates everything that comes back; nothing here is trusted.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

import httpx

from dockline_api.config import Settings


class LLMError(RuntimeError):
    """The provider failed or returned something that is not a JSON object."""


class LLM(Protocol):
    """A chat model that answers with one JSON object."""

    name: str

    async def complete_json(
        self, system: str, user: str, *, effort: str = "medium"
    ) -> dict[str, Any]:
        """Return the model's reply parsed as a JSON object."""
        ...


# Free tiers rate-limit by tokens per minute; wait (bounded) instead of failing.
MAX_RATE_LIMIT_RETRIES = 4
MAX_RATE_LIMIT_WAIT_SECONDS = 30.0


def retry_after_seconds(headers: httpx.Headers) -> float:
    """Seconds to wait after a 429, from Retry-After (default 5 s, capped)."""
    try:
        wait = float(headers.get("retry-after", "5"))
    except ValueError:
        wait = 5.0
    return min(max(wait, 1.0), MAX_RATE_LIMIT_WAIT_SECONDS)


def _parse_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise LLMError("model did not return JSON") from error
    if not isinstance(value, dict):
        raise LLMError("model did not return a JSON object")
    return value


class OpenAICompatibleLLM:
    """Groq (OpenAI-compatible chat completions with JSON mode)."""

    def __init__(
        self, http: httpx.AsyncClient, *, base_url: str, api_key: str, model: str, name: str
    ) -> None:
        """Configure the endpoint and model."""
        self._http = http
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self.model = model
        self.name = name

    async def complete_json(
        self, system: str, user: str, *, effort: str = "medium"
    ) -> dict[str, Any]:
        """Call chat completions in JSON mode at temperature 0 (retrying on 429)."""
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = effort
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            response = await self._http.post(
                self._url, headers={"Authorization": f"Bearer {self._key}"}, json=body
            )
            if response.status_code == 429 and attempt < MAX_RATE_LIMIT_RETRIES:
                await asyncio.sleep(retry_after_seconds(response.headers))
                continue
            break
        if response.status_code != 200:
            raise LLMError(f"{self.name}: HTTP {response.status_code}")
        return _parse_object(response.json()["choices"][0]["message"]["content"])


class GeminiLLM:
    """Google Gemini (generateContent with a JSON response type)."""

    name = "gemini"

    def __init__(self, http: httpx.AsyncClient, *, api_key: str, model: str) -> None:
        """Configure the model."""
        self._http = http
        self._key = api_key
        self.model = model

    async def complete_json(
        self, system: str, user: str, *, effort: str = "medium"
    ) -> dict[str, Any]:
        """Call generateContent with responseMimeType application/json."""
        response = await self._http.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self._key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
            },
        )
        if response.status_code != 200:
            raise LLMError(f"gemini: HTTP {response.status_code}")
        return _parse_object(response.json()["candidates"][0]["content"]["parts"][0]["text"])


class OllamaLLM:
    """A local model served by Ollama (format=json)."""

    name = "ollama"

    def __init__(self, http: httpx.AsyncClient, *, base_url: str, model: str) -> None:
        """Configure the server and model."""
        self._http = http
        self._url = base_url.rstrip("/") + "/api/chat"
        self.model = model

    async def complete_json(
        self, system: str, user: str, *, effort: str = "medium"
    ) -> dict[str, Any]:
        """Call /api/chat with JSON output."""
        response = await self._http.post(
            self._url,
            json={
                "model": self.model,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        if response.status_code != 200:
            raise LLMError(f"ollama: HTTP {response.status_code}")
        return _parse_object(response.json()["message"]["content"])


def build_llm(settings: Settings, http: httpx.AsyncClient) -> LLM:
    """Create the provider named by LLM_PROVIDER."""
    if settings.llm_provider == "groq":
        return OpenAICompatibleLLM(
            http,
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            name="groq",
        )
    if settings.llm_provider == "gemini":
        return GeminiLLM(
            http, api_key=settings.gemini_api_key.get_secret_value(), model=settings.gemini_model
        )
    return OllamaLLM(http, base_url=settings.ollama_base_url, model=settings.ollama_model)
