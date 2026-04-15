# AutoFlow

Manage autonomous execution mode for the current Claude Code session.

**Arguments:** $ARGUMENTS

## Routing

Parse the first word of the arguments to determine the subcommand, then execute the matching CLI call below. Resolve `AUTOFLOW_ROOT` from the environment, or derive it from this file's location (`../../` relative to `.claude/commands/autoflow.md`).

---

### `init`

Generate a starter `autoflow.config.json` in the current project root. Detects the project type (Python, Node, Go, Rust…) and fills in sensible defaults.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" init
```

If the file already exists, show its current contents and suggest edits instead of overwriting.

---

### `start [--profile <name>]`

Activate AutoFlow autonomous mode.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" start $ARGUMENTS
```

Show the user: active mode, profile, trusted paths, risk threshold, and what will be auto-approved vs. blocked.

---

### `stop`

Deactivate AutoFlow and save the session log.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" stop
```

Display session summary: auto-approved / notified / blocked counts, checkpoints created, path to saved log.

---

### `status`

Show current AutoFlow state and live session log summary.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" status
```

---

### `trust <path>`

Add a path to the session-level trusted zone (temporary — not written to config).

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

---

### `report`

Generate and display the full session audit report.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" report
git diff --stat HEAD
```

---

### `sprint <profile>`

Activate a named sprint profile (activates AutoFlow if not already active). Profiles are defined in the project's `autoflow.config.json`.

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" sprint $ARGUMENTS
```

List available profiles if no argument is given.

---

## If AutoFlow is not installed

Inform the user:
> AutoFlow is not installed. Clone https://github.com/your-org/waip-autoflow and run `bash scripts/setup.sh`.

## Resolving AUTOFLOW_ROOT

If the env var is not set, find it:
```python
from pathlib import Path
autoflow_root = Path(__file__).parent.parent.parent  # .claude/commands/ → plugin root
```
