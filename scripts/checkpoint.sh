#!/usr/bin/env bash
# AutoFlow Checkpoint Manager
# ===========================
# Creates a reversible git checkpoint before risky operations.
# Usage: checkpoint.sh <mode> <label>
#   mode: auto | manual
#   label: short description of the checkpoint

set -euo pipefail

MODE="${1:-manual}"
LABEL="${2:-checkpoint}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
TAG_NAME="autoflow/ckpt-${TIMESTAMP}-${LABEL}"
SESSION_FILE="${HOME}/.autoflow/session.json"
LOG_DIR="${HOME}/.autoflow/logs"

mkdir -p "${LOG_DIR}"

log() {
  echo "[AutoFlow Checkpoint] $*" >&2
}

# Ensure we're in a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  log "Not a git repo — skipping checkpoint"
  exit 0
fi

# Check for uncommitted changes
HAS_CHANGES=$(git status --porcelain 2>/dev/null | head -1)

if [[ -z "${HAS_CHANGES}" ]]; then
  # No changes — just tag the current HEAD
  CHECKPOINT_TYPE="tag-only"
  COMMIT_HASH=$(git rev-parse HEAD)
  log "No uncommitted changes — tagging HEAD as checkpoint"
else
  # Stage and stash changes in a WIP commit
  CHECKPOINT_TYPE="stash"
  STASH_MSG="AutoFlow checkpoint: ${LABEL} (${TIMESTAMP})"
  git stash push -m "${STASH_MSG}" --include-untracked > /dev/null 2>&1 || true
  STASH_REF=$(git stash list --format="%gd %s" | grep "${STASH_MSG}" | head -1 | awk '{print $1}')
  log "Stashed uncommitted changes: ${STASH_REF}"
fi

# Create a lightweight tag for the checkpoint
git tag "${TAG_NAME}" 2>/dev/null || {
  log "Tag already exists — appending counter"
  git tag "${TAG_NAME}-2" 2>/dev/null || true
}

COMMIT_HASH=$(git rev-parse HEAD)

# Record checkpoint in session file
if [[ -f "${SESSION_FILE}" ]]; then
  CHECKPOINT_ENTRY=$(python3 - <<EOF
import json, datetime

session_file = "${SESSION_FILE}"
with open(session_file) as f:
    session = json.load(f)

session.setdefault("checkpoints", []).append({
    "ts": datetime.datetime.now().isoformat(timespec="seconds"),
    "tag": "${TAG_NAME}",
    "commit": "${COMMIT_HASH}",
    "type": "${CHECKPOINT_TYPE}",
    "label": "${LABEL}",
    "mode": "${MODE}"
})

with open(session_file, "w") as f:
    json.dump(session, f, indent=2)

print("ok")
EOF
  )
fi

log "Checkpoint created: ${TAG_NAME} @ ${COMMIT_HASH}"
echo "${TAG_NAME}"
