"""Create or update .env from .env.example.

* Keys present in .env.example but missing from .env are appended (so pulling a new
  phase never leaves a service without its settings).
* Empty ``*_PASSWORD`` and ``*_SECRET`` values are filled with random hex, so every
  local stack gets its own credentials and nothing secret is ever committed.
* Existing values in .env are never changed. API keys for external services
  (``*_API_KEY``) are left empty for you to fill in.

Usage: ``python3 scripts/init_env.py [.env.example] [.env]`` (stdlib only).
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

GENERATED_SUFFIXES = ("_PASSWORD", "_SECRET")


def parse_keys(text: str) -> dict[str, str]:
    """Return KEY -> value for every ``KEY=value`` line (comments ignored)."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def render_line(key: str, value: str) -> str:
    """Return the .env line for a key, generating a value for empty secrets."""
    if not value and key.endswith(GENERATED_SUFFIXES):
        value = secrets.token_hex(24)
    return f"{key}={value}"


def sync(example_path: Path, env_path: Path) -> list[str]:
    """Append missing keys (and fill empty secrets) in env_path. Returns added keys."""
    example_text = example_path.read_text()
    current = parse_keys(env_path.read_text()) if env_path.exists() else {}
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    added: list[str] = []
    if not env_path.exists():
        # Fresh .env: keep the template's comments and layout.
        for line in example_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                line = render_line(key.strip(), value.strip())
                added.append(key.strip())
            lines.append(line)
    else:
        for key, value in parse_keys(example_text).items():
            if key not in current:
                lines.append(render_line(key, value))
                added.append(key)
    env_path.write_text("\n".join(lines) + "\n")
    return added


def main() -> int:
    """Command-line entry point."""
    example = Path(sys.argv[1] if len(sys.argv) > 1 else ".env.example")
    env = Path(sys.argv[2] if len(sys.argv) > 2 else ".env")
    added = sync(example, env)
    print(f"{env}: {len(added)} key(s) added" + (f" ({', '.join(added)})" if added else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
