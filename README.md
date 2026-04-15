# waip-autoflow

**Autonomous execution mode for Claude Code sprints.**

Defines zones of automatic trust so Claude can implement features without interrupting you for every file write or `pytest` run — while still hard-blocking destructive operations and maintaining a full audit trail.

---

## How it works

The plugin intercepts every Claude Code tool call through a `PreToolUse` hook and applies a 3-level decision engine:

| Level | Decision | When | Example |
|-------|----------|------|---------|
| 1 | **Auto-approve** | Operation is inside a trusted path or command list | Write to `src/`, run `pytest` |
| 2 | **Notify** | Notable but safe operation outside strict trust zone | `git commit`, `docker-compose restart` |
| 3 | **Hard stop** | Destructive or out-of-scope operation | `rm -rf`, `--force`, `.env` modification |

An optional **risk-verifier agent** handles gray zones — it scores ambiguous operations `low / medium / high` and feeds that back to the engine.

---

## Quick start

```bash
# 1. Clone or install
git clone <repo> ~/.claude/plugins/waip-autoflow
cd ~/.claude/plugins/waip-autoflow

# 2. Install hooks into ~/.claude/settings.json
bash scripts/setup.sh

# 3. Export the plugin root
export AUTOFLOW_ROOT="$PWD"

# 4. Start a Claude Code session and activate
/autoflow start
# or for the ETL sprint profile:
/autoflow sprint sprint-etl
```

---

## Slash commands

| Command | Description |
|---------|-------------|
| `/autoflow start` | Activate autonomous mode |
| `/autoflow stop` | Return to standard interactive mode |
| `/autoflow status` | Show active mode, zones, session log summary |
| `/autoflow trust <path>` | Add a path to the session trust zone |
| `/autoflow distrust <path>` | Remove a path from the session trust zone |
| `/autoflow checkpoint [label]` | Create a git checkpoint before a risky operation |
| `/autoflow report` | Generate full session audit report (actions + diffs) |
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

Edit `autoflow.config.json` in the plugin root (or copy it to your project root):

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
| `medium` | Allow obviously safe read-only commands, block the rest |
| `high` | Allow everything not explicitly blocked |

---

## MCP Audit Server

The plugin includes a stdio MCP server with four tools:

| Tool | Description |
|------|-------------|
| `get_session_log` | List all actions with timestamps, decisions, and reasons |
| `get_diff_summary` | Show git diff of files modified automatically |
| `rollback_to_checkpoint` | Restore repo state to a named checkpoint |
| `export_report` | Write a markdown audit report |

Configure it in your Claude Code session by adding `.mcp.json` to your project:

```json
{
  "mcpServers": {
    "autoflow-audit": {
      "command": "python3",
      "args": ["$AUTOFLOW_ROOT/mcp-server/server.py"]
    }
  }
}
```

---

## Architecture

```
waip-autoflow/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── hooks/
│   └── hooks.json           # PreToolUse, PostToolUse, Stop hook definitions
├── scripts/
│   ├── decision-engine.py   # 3-level rule engine (the core hook)
│   ├── post-tool-logger.py  # PostToolUse: tracks modified files
│   ├── session-stop.py      # Stop: marks turn boundaries in log
│   ├── autoflow-cli.py      # CLI for slash commands (start/stop/trust/etc.)
│   ├── checkpoint.sh        # Git checkpoint creation
│   └── setup.sh             # Installs hooks into ~/.claude/settings.json
├── skills/
│   ├── autoflow-control/
│   │   └── SKILL.md         # /autoflow start|stop|trust|status|checkpoint|report
│   └── autoflow-sprint/
│       └── SKILL.md         # /autoflow sprint <profile>
├── agents/
│   └── risk-verifier.md     # Haiku-based gray-zone risk scorer
├── mcp-server/
│   └── server.py            # MCP audit server (stdio JSON-RPC)
├── .mcp.json                # MCP server config reference
├── autoflow.config.json     # Default configuration
└── README.md
```

---

## Session state

The plugin writes session state to `~/.autoflow/session.json`. Past sessions are archived to `~/.autoflow/logs/session-<timestamp>.json` when you run `/autoflow stop`.

The state file tracks:
- `active` — whether AutoFlow is currently on
- `profile` — active sprint profile
- `trusted_paths_extra` — paths added via `/autoflow trust` for this session
- `checkpoints` — list of git checkpoints created during the session
- `modified_files` — files written/edited since session start
- `log` — full action log with timestamps, tool, decision, reason

---

## Concrete example (WAIP Sprint 2)

With `sprint-etl` active:

```
Claude implements WAIP-25 (RSS collector)
  → writes src/collectors/rss.py          ✅ auto-approved (trusted path)
  → runs pytest tests/test_rss.py         ✅ auto-approved (trusted command)
  → git add src/ && git commit -m "feat"  📋 notified in log, no interruption
  → tries to modify docker-compose.yml   📌 auto-checkpoint created
                                         🚫 hard stop → ask for confirmation
```

Zero manual interruptions for the 3 standard cases. Full audit trail throughout.

---

## Requirements

- Python 3.10+
- Git
- Claude Code with hooks support
