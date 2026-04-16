# waip-autoflow

**Autonomous execution mode for Claude Code sprints.**

Give Claude a list of tasks. It executes them start to finish — no permission dialogs, no "should I continue?", no "which approach do you prefer?". It stops only when it hits a genuine blocker or a destructive operation.

Works on any project, any language, any team.

---

## The problem

Claude Code interrupts in two ways:

1. **Permission dialogs** — "Can I run this command / write this file?" before every tool call
2. **Conversational checkpoints** — "I've completed WAIP-47. Should I continue with WAIP-48? 🚀"

Both destroy flow on a sprint. AutoFlow eliminates both.

---

## How to use it

Give Claude a complete backlog at the start of the session, then activate AutoFlow:

```
Implement WAIP-48 (Dashboard), WAIP-49 (Brand detail page), WAIP-50 (Export).
Specs are in the Linear tickets. Use the existing component library.

/autoflow sprint frontend
```

Claude will work through all three tickets autonomously. It writes files, runs tests, commits — without stopping to ask. The only things that interrupt it are genuine blockers:
- An operation explicitly hard-blocked by your config (`rm -rf`, `.env` writes, etc.)
- Something it genuinely cannot resolve without domain knowledge you haven't given it

Everything else, it decides and does.

---

## What AutoFlow actually does

**Removes permission dialogs** via `permissions.allow` in `~/.claude/settings.json`. Claude Code's native dialog layer is bypassed entirely — the hook takes over.

**Routes every tool call** through a 3-level decision engine (PreToolUse hook):

| Level | Decision | When | Example |
|-------|----------|------|---------|
| 1 | **Approve** | Inside trusted paths / commands | Write `src/`, run `pytest` |
| 2 | **Approve + log** | Notable but safe | `git commit`, `git push` |
| 3 | **Hard block** | Destructive or out-of-scope | `rm -rf`, `--force`, `.env` write |

Hard blocks are always active — even when AutoFlow is not started. Installing the plugin means `rm -rf` never slips through silently.

**What AutoFlow does NOT do:** decide what to build, resolve ambiguous requirements, or make high-level architectural choices. That's still your job, at the start of the session when you hand Claude the backlog.

---

## Installation

```bash
git clone <repo> ~/tools/waip-autoflow
cd ~/tools/waip-autoflow
bash scripts/setup.sh
source ~/.zshrc   # or ~/.bashrc
```

`setup.sh`:
1. Copies the `/autoflow` slash command to `~/.claude/commands/`
2. Adds `PreToolUse` / `PostToolUse` / `Stop` hooks to `~/.claude/settings.json`
3. Sets broad `permissions.allow` so Claude Code shows no native dialogs
4. Adds `AUTOFLOW_ROOT` to your shell profile

To uninstall: `bash scripts/setup.sh --uninstall`

---

## Configure for your project

From inside a Claude Code session:

```
/autoflow init
```

Detects your stack and writes `autoflow.config.json` at the project root. Edit it to add your own profiles:

```json
{
  "trusted_paths": ["src/", "tests/"],
  "trusted_commands": ["pytest", "npm run", "git add", "git commit"],
  "checkpoint_before": ["alembic upgrade", "docker-compose down"],
  "profiles": {
    "frontend": {
      "trusted_paths": ["src/components/", "src/pages/", "tests/"],
      "risk_threshold": "medium"
    },
    "backend": {
      "trusted_paths": ["src/api/", "tests/"],
      "risk_threshold": "low"
    }
  }
}
```

The config is re-read on every tool call — edits take effect immediately.

---

## Slash commands

| Command | Description |
|---------|-------------|
| `/autoflow init` | Generate `autoflow.config.json` for this project |
| `/autoflow start` | Activate autonomous mode |
| `/autoflow stop` | Deactivate + save session log |
| `/autoflow status` | Active mode, zones, live log summary |
| `/autoflow trust <path>` | Add a path to the session trust zone |
| `/autoflow distrust <path>` | Remove a path from the session trust zone |
| `/autoflow checkpoint [label]` | Create a git checkpoint manually |
| `/autoflow report` | Full session audit (actions + git diff) |
| `/autoflow sprint <profile>` | Activate a named profile |

---

## Built-in profiles

| Profile | Risk threshold | Trusted paths |
|---------|---------------|---------------|
| `sprint` | medium | `src/`, `tests/`, `test/` |
| `strict` | low | none — whitelist only |
| `review` | high | none — notify on everything |

---

## Risk threshold

| Value | Behaviour for unlisted commands |
|-------|--------------------------------|
| `low` | Block everything not on the whitelist |
| `medium` | Allow obvious read-only patterns, block the rest |
| `high` | Allow everything not explicitly blocked |

---

## MCP Audit Server

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

| Tool | Description |
|------|-------------|
| `get_session_log` | All approved / notified / blocked actions |
| `get_diff_summary` | Git diff of files modified automatically |
| `rollback_to_checkpoint` | Restore repo to a named checkpoint |
| `export_report` | Write a markdown audit report |

---

## Architecture

```
waip-autoflow/
├── .claude/
│   └── commands/
│       └── autoflow.md      # /autoflow slash command (→ ~/.claude/commands/)
├── scripts/
│   ├── decision-engine.py   # PreToolUse hook — 3-level rule engine
│   ├── post-tool-logger.py  # PostToolUse hook — tracks modified files
│   ├── session-stop.py      # Stop hook — marks turn boundaries in log
│   ├── autoflow-cli.py      # Backend for all /autoflow subcommands
│   ├── checkpoint.sh        # Git checkpoint creation
│   └── setup.sh             # Installer
├── agents/
│   └── risk-verifier.md     # Haiku risk scorer for gray zones
├── mcp-server/
│   └── server.py            # MCP audit server
├── autoflow.config.json     # Default config (override in project root)
└── README.md
```

---

## Session state

- Active: `~/.autoflow/session.json`
- Archived: `~/.autoflow/logs/session-<timestamp>.json`

---

## Requirements

- Python 3.10+
- Git
- Claude Code with hooks support
