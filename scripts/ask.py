"""Ask the running API a question and print the JSON answer (stdlib only).

Usage: ``python3 scripts/ask.py "How many stations are empty right now?"`` (or ``make ask Q=...``).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    """Send the question to POST /v1/ask and pretty-print the response."""
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print('usage: make ask Q="your question"')
        return 2
    url = f"http://localhost:{os.environ.get('API_PORT', '8070')}/v1/ask"
    request = urllib.request.Request(  # noqa: S310 - local API
        url,
        data=json.dumps({"question": sys.argv[1]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310
            print(json.dumps(json.loads(response.read()), indent=2))
    except urllib.error.HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode()}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
