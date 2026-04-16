#!/usr/bin/env bash
# AutoFlow Setup Script
# =====================
# Installs waip-autoflow into Claude Code by:
#   1. Adding PreToolUse/PostToolUse/Stop hooks to ~/.claude/settings.json
#   2. Copying the /autoflow slash command to ~/.claude/commands/autoflow.md
#   3. Adding the AUTOFLOW_ROOT line to your shell profile
#
# Usage:
#   bash setup.sh [--uninstall]

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="${HOME}/.claude"
CLAUDE_SETTINGS="${CLAUDE_DIR}/settings.json"
COMMANDS_DIR="${CLAUDE_DIR}/commands"
MARKER="waip-autoflow"

log()   { echo "[autoflow setup] $*"; }
error() { echo "[autoflow setup] ERROR: $*" >&2; }

# ---------------------------------------------------------------------------
# Uninstall mode
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--uninstall" ]]; then
  log "Uninstalling AutoFlow..."

  # Remove slash command
  if [[ -f "${COMMANDS_DIR}/autoflow.md" ]]; then
    rm "${COMMANDS_DIR}/autoflow.md"
    log "Removed ${COMMANDS_DIR}/autoflow.md"
  fi

  # Remove hooks and permissions from settings.json
  if [[ -f "${CLAUDE_SETTINGS}" ]]; then
    python3 - <<PYEOF
import json
with open("${CLAUDE_SETTINGS}") as f:
    settings = json.load(f)

# Remove hooks
hooks = settings.get("hooks", {})
for event in list(hooks.keys()):
    hooks[event] = [
        h for h in hooks[event]
        if h.get("_source") != "${MARKER}"
    ]
    if not hooks[event]:
        del hooks[event]
if not hooks:
    settings.pop("hooks", None)
else:
    settings["hooks"] = hooks

# Remove the broad permissions added by setup
autoflow_perms = ["Bash(*)", "Write(*)", "Edit(*)", "Read(*)", "Glob(*)", "Grep(*)", "NotebookEdit(*)", "Task(*)"]
if "permissions" in settings and "allow" in settings["permissions"]:
    settings["permissions"]["allow"] = [
        p for p in settings["permissions"]["allow"]
        if p not in autoflow_perms
    ]
    if not settings["permissions"]["allow"]:
        settings.pop("permissions", None)

with open("${CLAUDE_SETTINGS}", "w") as f:
    json.dump(settings, f, indent=2)
print("Hooks and permissions removed from settings.json")
PYEOF
  fi

  log "Done. Run 'unset AUTOFLOW_ROOT' to clean up your shell."
  exit 0
fi

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
log "Installing AutoFlow from: ${PLUGIN_ROOT}"

mkdir -p "${COMMANDS_DIR}"
mkdir -p "${HOME}/.autoflow/logs"

# 1. Install slash command: copy .claude/commands/autoflow.md to ~/.claude/commands/
COMMAND_SRC="${PLUGIN_ROOT}/.claude/commands/autoflow.md"
COMMAND_DST="${COMMANDS_DIR}/autoflow.md"

if [[ -f "${COMMAND_SRC}" ]]; then
  # Rewrite AUTOFLOW_ROOT placeholder in the copied file
  sed "s|\\\$AUTOFLOW_ROOT|${PLUGIN_ROOT}|g" "${COMMAND_SRC}" > "${COMMAND_DST}"
  log "Slash command installed: ${COMMAND_DST}"
else
  error "Command source not found: ${COMMAND_SRC}"
  exit 1
fi

# 2. Merge hooks into ~/.claude/settings.json
python3 - <<PYEOF
import json
from pathlib import Path

settings_path = Path("${CLAUDE_SETTINGS}")
plugin_root = "${PLUGIN_ROOT}"
marker = "${MARKER}"

settings = {}
if settings_path.exists():
    with open(settings_path) as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}

settings.setdefault("hooks", {})

def make_hook(script_name: str) -> dict:
    return {
        "type": "command",
        "command": f'AUTOFLOW_ROOT="{plugin_root}" python3 "{plugin_root}/scripts/{script_name}"',
    }

# PreToolUse — 3-level decision engine, fires on every tool call
settings["hooks"].setdefault("PreToolUse", [])
settings["hooks"]["PreToolUse"] = [
    h for h in settings["hooks"]["PreToolUse"]
    if h.get("_source") != marker
]
settings["hooks"]["PreToolUse"].append({
    "matcher": ".*",
    "hooks": [make_hook("decision-engine.py")],
    "_source": marker,
})

# PostToolUse — tracks modified files for the diff summary
settings["hooks"].setdefault("PostToolUse", [])
settings["hooks"]["PostToolUse"] = [
    h for h in settings["hooks"]["PostToolUse"]
    if h.get("_source") != marker
]
settings["hooks"]["PostToolUse"].append({
    "matcher": "Bash|Write|Edit|NotebookEdit",
    "hooks": [make_hook("post-tool-logger.py")],
    "_source": marker,
})

# Stop — marks turn boundaries in the session log
settings["hooks"].setdefault("Stop", [])
settings["hooks"]["Stop"] = [
    h for h in settings["hooks"]["Stop"]
    if h.get("_source") != marker
]
settings["hooks"]["Stop"].append({
    "hooks": [make_hook("session-stop.py")],
    "_source": marker,
})

settings_path.parent.mkdir(parents=True, exist_ok=True)
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print(f"Hooks written to {settings_path}")
PYEOF

# 2b. Add broad allow-permissions so Claude Code doesn't show dialogs for
#     tools that our hook already controls. The hook handles the actual
#     allow/block logic — permissions here just prevent the UI dialog layer.
python3 - <<PYEOF
import json
from pathlib import Path

settings_path = Path("${CLAUDE_SETTINGS}")
with open(settings_path) as f:
    settings = json.load(f)

# These are the tools AutoFlow intercepts. By pre-allowing them here,
# Claude Code won't show its own permission dialogs — the hook decides instead.
allow_list = [
    "Bash(*)",
    "Write(*)",
    "Edit(*)",
    "Read(*)",
    "Glob(*)",
    "Grep(*)",
    "NotebookEdit(*)",
    "Task(*)",
]

perms = settings.setdefault("permissions", {})
existing = perms.get("allow", [])
for entry in allow_list:
    if entry not in existing:
        existing.append(entry)
perms["allow"] = existing

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print(f"Permissions written to {settings_path}")
PYEOF

# 3. Suggest adding AUTOFLOW_ROOT to shell profile
SHELL_PROFILE=""
if [[ -f "${HOME}/.zshrc" ]]; then SHELL_PROFILE="${HOME}/.zshrc"
elif [[ -f "${HOME}/.bashrc" ]]; then SHELL_PROFILE="${HOME}/.bashrc"
elif [[ -f "${HOME}/.bash_profile" ]]; then SHELL_PROFILE="${HOME}/.bash_profile"
fi

EXPORT_LINE="export AUTOFLOW_ROOT=\"${PLUGIN_ROOT}\""
if [[ -n "${SHELL_PROFILE}" ]]; then
  if ! grep -qF "AUTOFLOW_ROOT" "${SHELL_PROFILE}"; then
    echo "" >> "${SHELL_PROFILE}"
    echo "# waip-autoflow" >> "${SHELL_PROFILE}"
    echo "${EXPORT_LINE}" >> "${SHELL_PROFILE}"
    log "Added AUTOFLOW_ROOT to ${SHELL_PROFILE}"
  else
    log "AUTOFLOW_ROOT already in ${SHELL_PROFILE}"
  fi
fi

log ""
log "✅  AutoFlow installed successfully!"
log ""
log "Slash command : /autoflow (available in all Claude Code sessions)"
log "Hooks         : PreToolUse + PostToolUse + Stop in ${CLAUDE_SETTINGS}"
log "Session logs  : ~/.autoflow/logs/"
log ""
log "Reload your shell then start Claude Code:"
log "  source ${SHELL_PROFILE:-~/.bashrc}"
log ""
log "First time in a session:"
log "  /autoflow start"
log "  /autoflow sprint sprint-etl   # for WAIP ETL sprint"
log ""
log "To uninstall: bash ${PLUGIN_ROOT}/scripts/setup.sh --uninstall"
