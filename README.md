# waip-autoflow

**Autonomous execution mode for Claude Code sprints.**

Lets Claude implement features without interrupting you for every file write or test run — while hard-blocking destructive operations and maintaining a full audit trail.

Works on any project, any language, any team.

---

## How it works

Every Claude Code tool call passes through a `PreToolUse` hook that applies a 3-level decision engine:

| Level | Decision | When | Example |
|-------|----------|------|---------|
| 1 | **Auto-approve** | Inside a trusted path or command | Write `src/`, run `pytest` |
| 2 | **Notify** | Notable but safe — logged, not blocked | `git commit`, `git push` |
| 3 | **Hard stop** | Destructive or out-of-scope | `rm -rf`, `--force`, `.env` write |

A lightweight **risk-verifier agent** (Haiku, `maxTurns: 1`) handles gray zones by returning a `low / medium / high` score with a one-line justification.

---

## Installation

```bash
# Clone anywhere on your machine
git clone <repo> ~/tools/waip-autoflow
cd ~/tools/waip-autoflow

# Install — hooks + slash command into ~/.claude/
bash scripts/setup.sh

# Reload your shell
source ~/.zshrc   # or ~/.bashrc
```

`setup.sh` does three things:
1. Copies `.claude/commands/autoflow.md` → `~/.claude/commands/autoflow.md` (global `/autoflow` command)
2. Merges `PreToolUse` / `PostToolUse` / `Stop` hooks into `~/.claude/settings.json`
3. Adds `export AUTOFLOW_ROOT=<path>` to your shell profile

To uninstall: `bash scripts/setup.sh --uninstall`

---

## Configure for your project

Drop an `autoflow.config.json` at the **project root** — it takes precedence over the plugin defaults:

```json
{
  "trusted_paths": ["src/", "tests/", "migrations/"],
  "trusted_commands": ["pytest", "alembic", "git add", "git commit", "make"],
  "checkpoint_before": ["alembic upgrade", "docker-compose down"],
  "notify_on": ["git commit", "git push"],
  "profiles": {
    "backend": {
      "trusted_paths": ["src/api/", "tests/"],
      "risk_threshold": "low"
    },
    "frontend": {
      "trusted_paths": ["src/components/", "src/pages/", "tests/"],
      "trusted_commands": ["npm run", "npx", "yarn"],
      "risk_threshold": "medium"
    }
  }
}
```

Profile names are yours to define — they match your sprints, features, or team conventions.

---

## Slash commands

Available globally in every Claude Code session after install.

| Command | Description |
|---------|-------------|
| `/autoflow start` | Activate autonomous mode |
| `/autoflow stop` | Deactivate + save session log |
| `/autoflow status` | Active mode, zones, live session summary |
| `/autoflow trust <path>` | Add a path to the session trust zone (not persisted) |
| `/autoflow distrust <path>` | Remove a path from the session trust zone |
| `/autoflow checkpoint [label]` | Create a git checkpoint before a risky operation |
| `/autoflow report` | Full session audit report (actions + git diff) |
| `/autoflow sprint <profile>` | Activate a named profile from your project config |

---

## Built-in profiles

The plugin ships three generic profiles as defaults. Override or extend them in your project's `autoflow.config.json`.

| Profile | Risk threshold | Trusted paths |
|---------|---------------|---------------|
| `sprint` | medium | `src/`, `tests/`, `test/` |
| `strict` | low | none (whitelist only) |
| `review` | high | none (notify on everything) |

---

## Risk threshold reference

| Value | Behaviour for commands not in the trusted list |
|-------|------------------------------------------------|
| `low` | Block everything not explicitly whitelisted |
| `medium` | Allow obvious read-only patterns, block the rest |
| `high` | Allow everything not explicitly blocked |

---

## MCP Audit Server

Add to your project's `.mcp.json` (or `~/.claude/mcp.json` globally):

```json
{
  "mcpServers": {
    "autoflow-audit": {
      "command": "python3",
      "args": ["${AUTOFLOW_ROOT}/mcp-server/server.py"]
    }
  }
}
```

| MCP Tool | Description |
|----------|-------------|
| `get_session_log` | All auto-approved / notified / blocked actions |
| `get_diff_summary` | Git diff of files modified automatically |
| `rollback_to_checkpoint` | Restore repo to a named checkpoint |
| `export_report` | Write a markdown audit report |

---

## Architecture

```
waip-autoflow/
├── .claude/
│   └── commands/
│       └── autoflow.md      # /autoflow slash command source
│                            # → copied to ~/.claude/commands/ by setup.sh
├── hooks/
│   └── hooks.json           # Reference format only
│                            # (actual hooks live in ~/.claude/settings.json)
├── scripts/
│   ├── decision-engine.py   # PreToolUse hook — 3-level rule engine
│   ├── post-tool-logger.py  # PostToolUse hook — tracks modified files
│   ├── session-stop.py      # Stop hook — marks turn boundaries
│   ├── autoflow-cli.py      # Backend for all /autoflow subcommands
│   ├── checkpoint.sh        # Git checkpoint creation
│   └── setup.sh             # Installer (hooks + command → ~/.claude/)
├── agents/
│   └── risk-verifier.md     # Haiku-based gray-zone risk scorer
├── mcp-server/
│   └── server.py            # MCP audit server (stdio JSON-RPC)
├── .mcp.json                # MCP config template
├── autoflow.config.json     # Default config (override in project root)
└── README.md
```

---

## Session state

- Active session: `~/.autoflow/session.json`
- Archived sessions: `~/.autoflow/logs/session-<timestamp>.json`

Each session tracks: profile, trusted path overrides, checkpoints, modified files, and a full timestamped action log.

---

## Requirements

- Python 3.10+
- Git
- Claude Code with hooks support
