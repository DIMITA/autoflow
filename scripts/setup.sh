#!/usr/bin/env bash
# AutoFlow Setup Script
# =====================
# Configures the AUTOFLOW_ROOT environment variable and installs
# the PreToolUse / PostToolUse / Stop hooks into ~/.claude/settings.json.
#
# Usage:
#   bash setup.sh [--uninstall]

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"
MARKER="waip-autoflow"

log()   { echo "[autoflow setup] $*"; }
error() { echo "[autoflow setup] ERROR: $*" >&2; }

# ---------------------------------------------------------------------------
# Uninstall mode
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--uninstall" ]]; then
  log "Removing AutoFlow hooks from ${CLAUDE_SETTINGS}..."
  if [[ -f "${CLAUDE_SETTINGS}" ]]; then
    python3 - <<EOF
import json, sys
with open("${CLAUDE_SETTINGS}") as f:
    settings = json.load(f)

hooks = settings.get("hooks", {})
for event in list(hooks.keys()):
    hooks[event] = [
        h for h in hooks[event]
        if not any("${MARKER}" in json.dumps(hook) for hook in h.get("hooks", []))
    ]
    if not hooks[event]:
        del hooks[event]
if not hooks:
    settings.pop("hooks", None)
else:
    settings["hooks"] = hooks

with open("${CLAUDE_SETTINGS}", "w") as f:
    json.dump(settings, f, indent=2)
print("Done.")
EOF
    log "Hooks removed."
  fi
  log "Uninstall complete. Run 'unset AUTOFLOW_ROOT' to clean up."
  exit 0
fi

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
log "Installing AutoFlow from: ${PLUGIN_ROOT}"

# Create ~/.claude if needed
mkdir -p "${HOME}/.claude"
mkdir -p "${HOME}/.autoflow/logs"

# Write or update settings.json
python3 - <<EOF
import json, os, sys
from pathlib import Path

settings_path = Path("${CLAUDE_SETTINGS}")
plugin_root = "${PLUGIN_ROOT}"
marker = "${MARKER}"

# Load or create settings
if settings_path.exists():
    with open(settings_path) as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}
else:
    settings = {}

settings.setdefault("hooks", {})

def make_hook(script_name: str) -> dict:
    cmd = f'AUTOFLOW_ROOT="{plugin_root}" python3 "{plugin_root}/scripts/{script_name}"'
    return {
        "type": "command",
        "command": cmd,
    }

# PreToolUse — decision engine on all tools
settings["hooks"].setdefault("PreToolUse", [])
pre_entry = {
    "matcher": ".*",
    "hooks": [make_hook("decision-engine.py")],
    "_source": marker,
}
# Remove old autoflow entries
settings["hooks"]["PreToolUse"] = [
    h for h in settings["hooks"]["PreToolUse"]
    if h.get("_source") != marker
]
settings["hooks"]["PreToolUse"].append(pre_entry)

# PostToolUse — logger on write/bash tools
settings["hooks"].setdefault("PostToolUse", [])
post_entry = {
    "matcher": "Bash|Write|Edit|NotebookEdit",
    "hooks": [make_hook("post-tool-logger.py")],
    "_source": marker,
}
settings["hooks"]["PostToolUse"] = [
    h for h in settings["hooks"]["PostToolUse"]
    if h.get("_source") != marker
]
settings["hooks"]["PostToolUse"].append(post_entry)

# Stop — session marker
settings["hooks"].setdefault("Stop", [])
stop_entry = {
    "hooks": [make_hook("session-stop.py")],
    "_source": marker,
}
settings["hooks"]["Stop"] = [
    h for h in settings["hooks"]["Stop"]
    if h.get("_source") != marker
]
settings["hooks"]["Stop"].append(stop_entry)

# Write back
settings_path.parent.mkdir(parents=True, exist_ok=True)
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print(f"Settings written to {settings_path}")
EOF

# Export AUTOFLOW_ROOT for the current shell
log ""
log "✅  AutoFlow installed successfully!"
log ""
log "To activate in your shell:"
log "  export AUTOFLOW_ROOT=\"${PLUGIN_ROOT}\""
log ""
log "Then start a Claude Code session and run:"
log "  /autoflow start"
log "  /autoflow sprint sprint-etl   (for ETL sprint profile)"
log ""
log "To uninstall: bash ${PLUGIN_ROOT}/scripts/setup.sh --uninstall"
