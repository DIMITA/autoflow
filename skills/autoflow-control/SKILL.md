# AutoFlow Control

Manage the AutoFlow autonomous execution mode for the current session.

## Usage

`/autoflow <subcommand> [arguments]`

**$ARGUMENTS**

## Subcommands

### `start [--profile <name>]`
Activate AutoFlow autonomous mode. Optionally specify a sprint profile.

Run:
```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" start $ARGUMENTS
```

Then show the user what was activated (mode, profile, trusted paths, risk threshold).

---

### `stop`
Deactivate AutoFlow and save the session report.

Run:
```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" stop
```

Show the session summary (actions auto-approved, notified, blocked, checkpoints).

---

### `status`
Show the current AutoFlow state, active profile, and session log summary.

Run:
```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" status
```

---

### `trust <path>`
Add a path to the session-level trusted zone (temporary, not saved to config).

Run:
```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" trust $ARGUMENTS
```

---

### `distrust <path>`
Remove a path from the session-level trusted zone.

Run:
```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" distrust $ARGUMENTS
```

---

### `checkpoint [label]`
Create a manual git checkpoint before a risky operation.

Run:
```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" checkpoint $ARGUMENTS
```

---

### `report`
Generate and display the full session audit report (actions + diffs).

Run:
```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" report
```

Also show a brief git diff summary of files modified during the session:
```bash
git diff --stat HEAD
```

---

## Instructions for Claude

1. Parse the first word of `$ARGUMENTS` to identify the subcommand.
2. Pass remaining arguments to the CLI.
3. If `AUTOFLOW_ROOT` is not set, use the plugin directory (find it relative to this SKILL.md: `../../`).
4. After running the command, display the output to the user clearly.
5. If the subcommand is unknown, list available commands.

## Environment

- `AUTOFLOW_ROOT` — root directory of the autoflow plugin (set during setup)
- Session state: `~/.autoflow/session.json`
- Config: `autoflow.config.json` in the plugin root or project root
