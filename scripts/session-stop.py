#!/usr/bin/env python3
"""
AutoFlow Stop hook — fires when Claude finishes responding.
Appends a turn marker to the session log so the report shows turn boundaries.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

SESSION_FILE = Path.home() / ".autoflow" / "session.json"


def main() -> None:
    if not SESSION_FILE.exists():
        sys.exit(0)

    with open(SESSION_FILE) as f:
        session = json.load(f)

    if not session.get("active", False):
        sys.exit(0)

    # Add a turn-end marker to the log
    session.setdefault("log", []).append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "decision": "turn_end",
        "tool": "—",
        "details": "",
        "reason": "Claude turn completed",
    })

    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)

    sys.exit(0)


if __name__ == "__main__":
    main()
