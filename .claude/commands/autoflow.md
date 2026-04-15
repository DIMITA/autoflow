# AutoFlow

Manage autonomous execution mode for the current Claude Code session.

**Arguments:** $ARGUMENTS

## Routing

Parse the first word of the arguments to determine the subcommand, then execute the matching CLI call below. `AUTOFLOW_ROOT` is the directory where waip-autoflow is installed (set by `setup.sh`, or derive it from this file: `../../` relative to `.claude/commands/autoflow.md`).

---

### `start [--profile <name>]`

Activate AutoFlow autonomous mode.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" start $ARGUMENTS
```

After running, show the user: active mode, profile, trusted paths, risk threshold, and what kinds of operations will be auto-approved vs. blocked.

---

### `stop`

Deactivate AutoFlow and save the session log.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" stop
```

Display the session summary: counts of auto-approved / notified / blocked actions, checkpoints created, and path to the saved log file.

---

### `status`

Show the current AutoFlow state and session log summary.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" status
```

---

### `trust <path>`

Add a path to the session-level trusted zone (temporary, not written to config).

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" trust $ARGUMENTS
```

---

### `distrust <path>`

Remove a path from the session trust zone.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" distrust $ARGUMENTS
```

---

### `checkpoint [label]`

Create a manual git checkpoint before a risky operation.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" checkpoint $ARGUMENTS
```

Display the created tag name.

---

### `report`

Generate and display the full session audit report.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" report
```

Then show a git diff summary of files modified during the session:

```bash
git diff --stat HEAD
```

---

### `sprint <profile>`

Activate a named sprint profile (activates AutoFlow if not already active).

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" sprint $ARGUMENTS
```

List available profiles if no argument is given.

---

## Resolving AUTOFLOW_ROOT

If `AUTOFLOW_ROOT` is not set in the environment, resolve it programmatically:

```python
from pathlib import Path
# This file is at <plugin_root>/.claude/commands/autoflow.md
autoflow_root = Path(__file__).parent.parent.parent
```

Or ask the user to set it: `export AUTOFLOW_ROOT=/path/to/waip-autoflow`

## If AutoFlow is not installed

If `autoflow-cli.py` is not found, inform the user:
> AutoFlow is not installed. Clone the repo and run `bash scripts/setup.sh`.
