#!/usr/bin/env python3
"""
AutoFlow Decision Engine — PreToolUse hook
==========================================
Reads hook input from stdin (JSON), applies the 3-level rule engine,
outputs a JSON decision to stdout.

Decision levels:
  allow     — silent auto-approve, no interruption
  notify    — log to audit trail, execution continues
  block     — hard stop, Claude must ask for explicit confirmation
  checkpoint — create git checkpoint, then allow
"""

import json
import sys
import os
import re
from datetime import datetime
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PLUGIN_ROOT / "autoflow.config.json"
SESSION_FILE = Path.home() / ".autoflow" / "session.json"


# ---------------------------------------------------------------------------
# Config & session helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    # Look for config in the current project root too
    project_config = Path.cwd() / "autoflow.config.json"
    if project_config.exists():
        try:
            with open(project_config) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_session() -> dict:
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"active": False}


def save_session(session: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)


def get_effective_config(config: dict, session: dict) -> dict:
    """Merge base config with the active sprint profile (if any)."""
    effective = {
        "trusted_paths": list(config.get("trusted_paths", [])),
        "trusted_commands": list(config.get("trusted_commands", [])),
        "blocked_patterns": list(config.get("blocked_patterns", [])),
        "sensitive_files": list(config.get("sensitive_files", [])),
        "notify_on": list(config.get("notify_on", [])),
        "checkpoint_before": list(config.get("checkpoint_before", [])),
        "risk_threshold": config.get("risk_threshold", "medium"),
    }

    profile_name = session.get("profile")
    if profile_name:
        profiles = config.get("profiles", {})
        profile = profiles.get(profile_name, {})
        if "trusted_paths" in profile:
            effective["trusted_paths"] = list(profile["trusted_paths"])
        if "risk_threshold" in profile:
            effective["risk_threshold"] = profile["risk_threshold"]
        if "notify_on" in profile:
            effective["notify_on"] = list(profile["notify_on"])
        if "blocked_patterns" in profile:
            effective["blocked_patterns"] = list(profile["blocked_patterns"])

    # Merge session-level extra trusted paths
    extra = session.get("trusted_paths_extra", [])
    effective["trusted_paths"] = list(set(effective["trusted_paths"] + extra))

    return effective


# ---------------------------------------------------------------------------
# Tool input parsing helpers
# ---------------------------------------------------------------------------

def extract_file_path(tool_name: str, tool_input: dict) -> str | None:
    if tool_name in ("Write", "Edit", "Read", "Glob"):
        return tool_input.get("file_path") or tool_input.get("path")
    if tool_name == "NotebookEdit":
        return tool_input.get("notebook_path")
    return None


def extract_command(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        return tool_input.get("command", "")
    return ""


def is_trusted_path(file_path: str, trusted_paths: list[str]) -> bool:
    p = file_path.lstrip("/").lstrip("./")
    for trusted in trusted_paths:
        t = trusted.rstrip("/")
        if p.startswith(t) or p.startswith(trusted) or ("/" + t + "/") in ("/" + p):
            return True
    return False


def matches_any(text: str, patterns: list[str]) -> str | None:
    """Return the first matched pattern or None."""
    text_lower = text.lower()
    for pattern in patterns:
        if pattern.lower() in text_lower:
            return pattern
    return None


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------

def log_action(session: dict, decision: str, tool_name: str, details: str, reason: str) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "tool": tool_name,
        "details": details[:200],
        "reason": reason,
    }
    session.setdefault("log", []).append(entry)
    save_session(session)


# ---------------------------------------------------------------------------
# Core 3-level decision engine
# ---------------------------------------------------------------------------

def decide(tool_name: str, tool_input: dict, effective: dict) -> tuple[str, str]:
    """
    Returns (decision, reason) where decision is one of:
        allow | notify | block | checkpoint
    """
    blocked_patterns = effective["blocked_patterns"]
    trusted_paths = effective["trusted_paths"]
    trusted_commands = effective["trusted_commands"]
    sensitive_files = effective["sensitive_files"]
    notify_on = effective["notify_on"]
    checkpoint_before = effective["checkpoint_before"]
    risk_threshold = effective["risk_threshold"]

    # -----------------------------------------------------------------------
    # Level 3 — Hard blocks (always active, regardless of profile)
    # -----------------------------------------------------------------------

    command = extract_command(tool_name, tool_input)
    file_path = extract_file_path(tool_name, tool_input)

    # Block on destructive command patterns
    if command:
        matched = matches_any(command, blocked_patterns)
        if matched:
            return "block", f"Destructive pattern blocked: `{matched}`"

        # Checkpoint before risky but allowed operations
        for trigger in checkpoint_before:
            if trigger.lower() in command.lower():
                return "checkpoint", f"Checkpoint required before: `{trigger}`"

    # Block sensitive file modifications
    if file_path and tool_name in ("Write", "Edit", "NotebookEdit"):
        basename = os.path.basename(file_path)
        full = file_path.replace("\\", "/")
        for sf in sensitive_files:
            if basename == sf or full.endswith("/" + sf):
                return "block", f"Sensitive file modification blocked: `{file_path}`"

    # -----------------------------------------------------------------------
    # Level 1 — Auto-approve (trusted zone)
    # -----------------------------------------------------------------------

    # File operations inside trusted paths
    if file_path and tool_name in ("Write", "Edit", "NotebookEdit"):
        if is_trusted_path(file_path, trusted_paths):
            return "allow", f"Trusted path: `{file_path}`"
        else:
            if risk_threshold == "low":
                return "block", f"Path outside trusted zone (low threshold): `{file_path}`"
            return "block", f"Path not in trusted zone: `{file_path}`"

    # Read-only file ops are always fine
    if tool_name in ("Read", "Glob", "Grep"):
        return "allow", f"Read-only operation"

    # Bash commands
    if tool_name == "Bash":
        if not command:
            return "allow", "Empty command"

        cmd_stripped = command.strip()

        # Check explicit trusted commands
        for tc in trusted_commands:
            if cmd_stripped.startswith(tc) or (" " + tc + " ") in (" " + cmd_stripped + " "):
                # Sub-check: should we notify?
                if "*" in notify_on or matches_any(command, notify_on):
                    return "notify", f"Trusted command (notify): `{tc}`"
                return "allow", f"Trusted command: `{tc}`"

        # Risk threshold decides fate of untrusted commands
        if risk_threshold == "low":
            return "block", f"Untrusted command (low threshold): `{cmd_stripped[:80]}`"
        elif risk_threshold == "medium":
            # Allow obviously safe read-only shell patterns
            safe_prefixes = ("ls", "cat ", "echo ", "pwd", "which ", "python", "node ", "npm run ", "make ", "curl ")
            for sp in safe_prefixes:
                if cmd_stripped.startswith(sp):
                    return "notify", f"Untrusted but safe-looking command: `{cmd_stripped[:80]}`"
            return "block", f"Untrusted command (medium threshold): `{cmd_stripped[:80]}`"
        else:
            # high threshold — allow everything not explicitly blocked
            return "notify", f"Allowed under high threshold: `{cmd_stripped[:80]}`"

    # Default: allow agent-internal tools (Agent, Task, etc.)
    return "allow", f"Default allow: `{tool_name}`"


# ---------------------------------------------------------------------------
# Checkpoint runner
# ---------------------------------------------------------------------------

def run_checkpoint(reason: str) -> None:
    """Trigger checkpoint.sh asynchronously before allowing the operation."""
    import subprocess
    checkpoint_script = PLUGIN_ROOT / "scripts" / "checkpoint.sh"
    if checkpoint_script.exists():
        label = re.sub(r"[^a-zA-Z0-9_-]", "-", reason[:40]).strip("-")
        subprocess.run(
            ["bash", str(checkpoint_script), "auto", label],
            capture_output=True,
            timeout=15,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        input_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name: str = input_data.get("tool_name", "")
    tool_input: dict = input_data.get("tool_input", {})

    config = load_config()
    session = load_session()

    # If AutoFlow is not active, pass through — don't interfere
    if not session.get("active", False):
        sys.exit(0)

    effective = get_effective_config(config, session)
    decision, reason = decide(tool_name, tool_input, effective)

    # Build audit details
    command = extract_command(tool_name, tool_input)
    file_path = extract_file_path(tool_name, tool_input)
    details = command or file_path or str(tool_input)[:100]

    if decision == "checkpoint":
        # Create checkpoint, log it, then allow
        log_action(session, "checkpoint", tool_name, details, reason)
        session = load_session()  # reload after save
        try:
            run_checkpoint(reason)
        except Exception:
            pass
        log_action(session, "allow", tool_name, details, f"After auto-checkpoint: {reason}")
        sys.exit(0)

    log_action(session, decision, tool_name, details, reason)

    if decision == "block":
        output = {
            "decision": "block",
            "reason": f"[AutoFlow] {reason}",
        }
        print(json.dumps(output))
        sys.exit(0)

    if decision == "notify":
        # Print to stderr so it shows as a subtle note, not a block
        print(f"[AutoFlow] {reason}", file=sys.stderr)
        sys.exit(0)

    # allow — silent exit 0
    sys.exit(0)


if __name__ == "__main__":
    main()
