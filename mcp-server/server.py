#!/usr/bin/env python3
"""
AutoFlow Audit MCP Server
=========================
Exposes audit and rollback tools over the MCP stdio protocol.

Tools:
  get_session_log       — list all auto-approved/notified/blocked actions
  get_diff_summary      — show files modified automatically since session start
  rollback_to_checkpoint — restore git state to a named checkpoint
  export_report         — generate markdown report file
"""

import json
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path

SESSION_FILE = Path.home() / ".autoflow" / "session.json"
LOGS_DIR = Path.home() / ".autoflow" / "logs"

# ---------------------------------------------------------------------------
# MCP protocol helpers (stdio JSON-RPC 2.0)
# ---------------------------------------------------------------------------

def send(obj: dict) -> None:
    line = json.dumps(obj)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def send_error(req_id, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def send_result(req_id, result: dict) -> None:
    send({"jsonrpc": "2.0", "id": req_id, "result": result})


def tool_result(content: str) -> dict:
    return {"content": [{"type": "text", "text": content}]}


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def load_session(session_ref: str | None = None) -> dict:
    if session_ref:
        # Try to load a saved session log
        path = LOGS_DIR / session_ref if not session_ref.startswith("/") else Path(session_ref)
        if path.exists():
            with open(path) as f:
                return json.load(f)

    if SESSION_FILE.exists():
        with open(SESSION_FILE) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_get_session_log(params: dict) -> str:
    session_ref = params.get("session_ref")
    filter_decision = params.get("filter")  # allow | notify | block | checkpoint | all
    limit = int(params.get("limit", 100))

    session = load_session(session_ref)
    log = session.get("log", [])

    if filter_decision and filter_decision != "all":
        log = [e for e in log if e.get("decision") == filter_decision]

    log = log[-limit:]

    if not log:
        return "No log entries found."

    lines = [
        f"AutoFlow Session Log — {len(log)} entries",
        f"Started: {session.get('started_at', 'unknown')} | Profile: {session.get('profile') or 'default'}",
        "",
    ]
    for entry in log:
        icon = {"allow": "✅", "notify": "📋", "block": "🚫", "checkpoint": "📌", "turn_end": "─"}.get(
            entry.get("decision", ""), "?"
        )
        lines.append(
            f"{icon} [{entry.get('ts', '')}] {entry.get('tool', ''):<16} | "
            f"{entry.get('decision', ''):<10} | {entry.get('reason', '')}"
        )

    return "\n".join(lines)


def tool_get_diff_summary(params: dict) -> str:
    session = load_session()
    modified_files = session.get("modified_files", [])
    checkpoints = session.get("checkpoints", [])

    lines = []

    # Git diff from oldest checkpoint or HEAD~n
    try:
        if checkpoints:
            ref = checkpoints[0]["commit"]
            result = subprocess.run(
                ["git", "diff", "--stat", ref, "HEAD"],
                capture_output=True, text=True, timeout=10
            )
        else:
            result = subprocess.run(
                ["git", "diff", "--stat"],
                capture_output=True, text=True, timeout=10
            )
        if result.returncode == 0 and result.stdout.strip():
            lines.append("## Git diff summary\n")
            lines.append(result.stdout)
    except Exception as e:
        lines.append(f"(git diff failed: {e})")

    if modified_files:
        lines.append("\n## Files modified by AutoFlow this session\n")
        for f in modified_files:
            lines.append(f"  - {f}")

    return "\n".join(lines) if lines else "No modifications tracked yet."


def tool_rollback_to_checkpoint(params: dict) -> str:
    tag = params.get("tag")
    if not tag:
        # List available checkpoints
        session = load_session()
        checkpoints = session.get("checkpoints", [])
        if not checkpoints:
            return "No checkpoints available."
        lines = ["Available checkpoints:"]
        for cp in checkpoints:
            lines.append(f"  📌 {cp['tag']} — {cp['ts']} ({cp.get('label', '')})")
        lines.append("\nCall rollback_to_checkpoint with tag=<tag> to restore.")
        return "\n".join(lines)

    try:
        # Verify the tag exists
        result = subprocess.run(
            ["git", "rev-parse", tag],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return f"Tag not found: {tag}"

        commit = result.stdout.strip()

        # Check for uncommitted changes
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10
        )
        if status.stdout.strip():
            # Stash current state first
            subprocess.run(
                ["git", "stash", "push", "-m", f"Pre-rollback stash ({datetime.now().isoformat(timespec='seconds')})"],
                capture_output=True, timeout=10
            )

        # Reset to checkpoint
        reset = subprocess.run(
            ["git", "reset", "--hard", commit],
            capture_output=True, text=True, timeout=30
        )
        if reset.returncode == 0:
            return f"✅  Rolled back to {tag} ({commit[:8]})\n{reset.stdout.strip()}"
        else:
            return f"❌  Rollback failed: {reset.stderr.strip()}"
    except Exception as e:
        return f"❌  Error during rollback: {e}"


def tool_export_report(params: dict) -> str:
    output_path = params.get("path", ".autoflow-report.md")
    session = load_session()
    log = session.get("log", [])

    if not log:
        return "No session log to export."

    lines = [
        "# AutoFlow Session Report\n",
        f"**Generated**: {datetime.now().isoformat(timespec='seconds')}  ",
        f"**Started**: {session.get('started_at', 'unknown')}  ",
        f"**Profile**: {session.get('profile') or 'default'}  ",
        f"**Mode**: {session.get('mode', 'sprint')}  \n",
        "## Summary\n",
        "| Decision | Count |",
        "|----------|-------|",
        f"| ✅ Auto-approved | {sum(1 for e in log if e.get('decision') == 'allow')} |",
        f"| 📋 Notified | {sum(1 for e in log if e.get('decision') == 'notify')} |",
        f"| 🚫 Blocked | {sum(1 for e in log if e.get('decision') == 'block')} |",
        f"| 📌 Checkpoints | {len(session.get('checkpoints', []))} |",
        "",
    ]

    checkpoints = session.get("checkpoints", [])
    if checkpoints:
        lines.append("## Checkpoints\n")
        for cp in checkpoints:
            lines.append(f"- `{cp['tag']}` — {cp['ts']} ({cp.get('label', '')})")
        lines.append("")

    modified = session.get("modified_files", [])
    if modified:
        lines.append("## Modified Files\n")
        for f in modified:
            lines.append(f"- `{f}`")
        lines.append("")

    lines.append("## Full Action Log\n")
    lines.append("| Time | Decision | Tool | Reason |")
    lines.append("|------|----------|------|--------|")
    for entry in log:
        if entry.get("decision") == "turn_end":
            continue
        icon = {"allow": "✅", "notify": "📋", "block": "🚫", "checkpoint": "📌"}.get(entry.get("decision", ""), "?")
        ts = entry.get("ts", "")
        tool = entry.get("tool", "")
        reason = entry.get("reason", "").replace("|", "\\|")
        lines.append(f"| {ts} | {icon} {entry.get('decision', '')} | {tool} | {reason} |")

    content = "\n".join(lines) + "\n"
    path = Path(output_path)
    path.write_text(content)

    return f"✅  Report exported to: {path.resolve()}\n({len(log)} entries, {len(content)} bytes)"


# ---------------------------------------------------------------------------
# MCP dispatch
# ---------------------------------------------------------------------------

TOOLS = {
    "get_session_log": {
        "description": "List all auto-approved, notified, and blocked actions from the current or a past AutoFlow session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_ref": {"type": "string", "description": "Optional: filename of a saved session log in ~/.autoflow/logs/"},
                "filter": {"type": "string", "enum": ["allow", "notify", "block", "checkpoint", "all"], "description": "Filter by decision type"},
                "limit": {"type": "integer", "description": "Maximum number of entries to return (default 100)"},
            },
        },
        "handler": tool_get_session_log,
    },
    "get_diff_summary": {
        "description": "Show a git diff summary of files modified automatically since the session started.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_get_diff_summary,
    },
    "rollback_to_checkpoint": {
        "description": "Restore the git repository to a named AutoFlow checkpoint. Without a tag, lists available checkpoints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {"type": "string", "description": "The git tag name (e.g. autoflow/ckpt-20250415-143022-pre-migration)"},
            },
        },
        "handler": tool_rollback_to_checkpoint,
    },
    "export_report": {
        "description": "Generate a markdown audit report of the AutoFlow session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Output file path (default: .autoflow-report.md)"},
            },
        },
        "handler": tool_export_report,
    },
}


def handle_request(req: dict) -> None:
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "initialize":
        send_result(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "autoflow-audit", "version": "1.0.0"},
        })
        return

    if method == "tools/list":
        tools_list = []
        for name, spec in TOOLS.items():
            tools_list.append({
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            })
        send_result(req_id, {"tools": tools_list})
        return

    if method == "tools/call":
        tool_name = params.get("name")
        tool_params = params.get("arguments", {})
        spec = TOOLS.get(tool_name)
        if not spec:
            send_error(req_id, -32601, f"Tool not found: {tool_name}")
            return
        try:
            text = spec["handler"](tool_params)
            send_result(req_id, tool_result(text))
        except Exception as e:
            send_error(req_id, -32603, f"Tool execution failed: {e}")
        return

    if method == "notifications/initialized":
        return  # no response needed

    send_error(req_id, -32601, f"Unknown method: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle_request(req)


if __name__ == "__main__":
    main()
