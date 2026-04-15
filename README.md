# waip-autoflow

**Autonomous execution mode for Claude Code sprints.**

Defines zones of automatic trust so Claude can implement features without interrupting you for every file write or `pytest` run — while still hard-blocking destructive operations and maintaining a full audit trail.

---

## How it works

The plugin intercepts every Claude Code tool call through a `PreToolUse` hook and applies a 3-level decision engine:

| Level | Decision | When | Example |
|-------|----------|------|---------|
| 1 | **Auto-approve** | Operation is inside a trusted path or command list | Write to `src/`, run `pytest` |
| 2 | **Notify** | Notable but safe operation — logged, not blocked | `git commit`, `docker-compose restart` |
| 3 | **Hard stop** | Destructive or out-of-scope operation | `rm -rf`, `--force`, `.env` modification |

A lightweight **risk-verifier agent** (Haiku) handles gray zones — it scores ambiguous operations `low / medium / high` and feeds that back to the engine.

---

## Installation

```bash
# 1. Clone anywhere on your machine
git clone <repo> ~/tools/waip-autoflow
cd ~/tools/waip-autoflow

# 2. Run setup — installs hooks + /autoflow command into ~/.claude/
bash scripts/setup.sh

# 3. Reload your shell
source ~/.zshrc   # or ~/.bashrc

# 4. Open Claude Code — the /autoflow command is now available globally
```

`setup.sh` does three things:
- Copies `.claude/commands/autoflow.md` → `~/.claude/commands/autoflow.md` (global slash command)
- Merges `PreToolUse` / `PostToolUse` / `Stop` hooks into `~/.claude/settings.json`
- Adds `export AUTOFLOW_ROOT=<path>` to your shell profile

To uninstall: `bash scripts/setup.sh --uninstall`

---

## Slash commands

All commands are available in every Claude Code session after installation.

| Command | Description |
|---------|-------------|
| `/autoflow start` | Activate autonomous mode |
| `/autoflow stop` | Return to standard interactive mode + save session log |
| `/autoflow status` | Show active mode, zones, and session log summary |
| `/autoflow trust <path>` | Add a path to the session trust zone (temporary) |
| `/autoflow distrust <path>` | Remove a path from the session trust zone |
| `/autoflow checkpoint [label]` | Create a git checkpoint before a risky operation |
| `/autoflow report` | Full session audit report (actions + diffs) |
| `/autoflow sprint <profile>` | Activate a named sprint profile |

---

## Sprint profiles

Defined in `autoflow.config.json` under `profiles`:

| Profile | Risk threshold | Trusted paths |
|---------|---------------|---------------|
| `sprint-etl` | low | `src/collectors/`, `src/etl/`, `tests/` |
| `sprint-full` | medium | `src/`, `tests/`, `collectors/`, `etl/`, `scripts/` |
| `review` | high | none (notify on everything) |
| `safe` | high | none (extra blocked patterns) |

---

## Configuration

`autoflow.config.json` in the plugin root controls defaults. Copy it to your project root to override per-project:

```json
{
  "mode": "sprint",
  "risk_threshold": "medium",
  "trusted_paths": ["src/", "tests/"],
  "trusted_commands": ["pytest", "git add", "git commit", "pip install"],
  "blocked_patterns": ["rm -rf", "--force", "DROP TABLE"],
  "notify_on": ["git commit", "docker-compose restart"],
  "profiles": {
    "my-sprint": {
      "trusted_paths": ["src/feature-x/"],
      "risk_threshold": "low"
    }
  },
  "checkpoint_before": ["alembic upgrade", "docker-compose down"]
}
```

### Risk threshold

| Value | Behaviour for untrusted commands |
|-------|----------------------------------|
| `low` | Block everything not in the whitelist |
| `medium` | Allow obvious read-only commands, block the rest |
| `high` | Allow everything not explicitly blocked |

---

## MCP Audit Server

Add `.mcp.json` to your project root (or `~/.claude/mcp.json` globally) to enable the audit tools:

```json
{
  "mcpServers": {
    "autoflow-audit": {
      "command": "python3",
      "args": ["/path/to/waip-autoflow/mcp-server/server.py"]
    }
  }
}
```

Available MCP tools:

| Tool | Description |
|------|-------------|
| `get_session_log` | List all auto-approved / notified / blocked actions |
| `get_diff_summary` | Git diff of files modified automatically |
| `rollback_to_checkpoint` | Restore repo to a named checkpoint |
| `export_report` | Write a markdown audit report |

---

## Architecture

```
waip-autoflow/
├── .claude/
│   └── commands/
│       └── autoflow.md      # /autoflow slash command (copied to ~/.claude/commands/ by setup.sh)
├── hooks/
│   └── hooks.json           # Reference format (actual hooks live in ~/.claude/settings.json)
├── scripts/
│   ├── decision-engine.py   # PreToolUse hook — 3-level rule engine
│   ├── post-tool-logger.py  # PostToolUse hook — tracks modified files
│   ├── session-stop.py      # Stop hook — marks turn boundaries in log
│   ├── autoflow-cli.py      # Backend for all /autoflow subcommands
│   ├── checkpoint.sh        # Git checkpoint creation
│   └── setup.sh             # Installs into ~/.claude/ (commands + settings.json)
├── agents/
│   └── risk-verifier.md     # Haiku-based gray-zone risk scorer (maxTurns: 1)
├── mcp-server/
│   └── server.py            # MCP audit server (stdio JSON-RPC 2024-11-05)
├── .mcp.json                # MCP config template (copy to project root)
├── autoflow.config.json     # Default configuration
└── README.md
```

---

## Session state

- Active session: `~/.autoflow/session.json`
- Past sessions: `~/.autoflow/logs/session-<timestamp>.json` (saved on `/autoflow stop`)

Tracked fields: `active`, `profile`, `trusted_paths_extra`, `checkpoints`, `modified_files`, `log` (full action history with timestamps, tool, decision, reason).

---

## Concrete example — WAIP Sprint 2 with `sprint-etl`

```
/autoflow sprint sprint-etl

Claude implements WAIP-25 (RSS collector):
  writes src/collectors/rss.py          ✅ auto-approved  (trusted path)
  runs pytest tests/test_rss.py         ✅ auto-approved  (trusted command)
  git add src/ && git commit -m "feat"  📋 notified       (in log, no interruption)
  tries to modify docker-compose.yml    📌 auto-checkpoint created
                                        🚫 hard stop → asks for confirmation
```

Zero manual interruptions for the standard flow. Full audit trail throughout.

---

## Requirements

- Python 3.10+
- Git
- Claude Code with hooks support (`~/.claude/settings.json`)
