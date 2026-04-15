# AutoFlow Sprint

Activate a named sprint profile — a pre-configured set of trusted paths and risk rules optimised for a specific sprint context.

## Usage

`/autoflow sprint <profile>`

**$ARGUMENTS**

## Behaviour

1. If `$ARGUMENTS` is empty, list all available profiles from `autoflow.config.json`.
2. Otherwise activate the named profile:

```bash
python3 "$AUTOFLOW_ROOT/scripts/autoflow-cli.py" sprint $ARGUMENTS
```

## Instructions for Claude

- Parse `$ARGUMENTS` as the profile name.
- Run the CLI command above (resolve `AUTOFLOW_ROOT` from this file's location if the env var is not set: `../../`).
- After activation, display:
  - Profile name and risk threshold
  - Trusted paths for this sprint
  - Which actions will be auto-approved vs. blocked
- Encourage the user to run `/autoflow status` to verify.

## Built-in Profiles

| Profile | Risk threshold | Trusted paths |
|---------|---------------|---------------|
| `sprint-etl` | low | `src/collectors/`, `src/etl/`, `tests/` |
| `sprint-full` | medium | `src/`, `tests/`, `collectors/`, `etl/`, `scripts/` |
| `review` | high | none (notify on everything) |
| `safe` | high | none (block rm/drop/delete/force) |

## Notes

- Sprint profiles can be extended in `autoflow.config.json` under `profiles`.
- Activating a sprint profile starts AutoFlow if it wasn't already active.
- The profile applies for the current session only.
