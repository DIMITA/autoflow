#!/usr/bin/env python3
"""
AutoFlow PostToolUse hook — logs successful tool executions.
Receives: {"tool_name", "tool_input", "tool_response", "session_id"}
"""

import json
import sys
from datetime import datetime
from pathlib import Path

SESSION_FILE = Path.home() / ".autoflow" / "session.json"


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if not SESSION_FILE.exists():
        sys.exit(0)

    with open(SESSION_FILE) as f:
        session = json.load(f)

    if not session.get("active", False):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Update stats
    stats = session.setdefault("stats", {"writes": 0, "commands": 0, "reads": 0})
    if tool_name in ("Write", "Edit", "NotebookEdit"):
        stats["writes"] += 1
        # Track modified files
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if path:
            session.setdefault("modified_files", [])
            if path not in session["modified_files"]:
                session["modified_files"].append(path)
    elif tool_name == "Bash":
        stats["commands"] += 1
    elif tool_name in ("Read", "Glob", "Grep"):
        stats["reads"] += 1

    session["last_action_at"] = datetime.now().isoformat(timespec="seconds")

    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)

    sys.exit(0)


if __name__ == "__main__":
    main()
