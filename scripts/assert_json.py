"""CI helper: read JSON on stdin and fail unless a numeric key is greater than zero.

Usage: ``curl ... | python3 scripts/assert_json.py stations``.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    """Print the key's value; exit 1 when it is missing or not positive."""
    key = sys.argv[1]
    value = json.load(sys.stdin).get(key)
    print(f"{key} = {value}")
    return 0 if isinstance(value, int | float) and value > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
