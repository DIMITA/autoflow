#!/usr/bin/env python3
"""
AutoFlow CLI — session management commands
==========================================
Invoked by SKILL.md slash commands:
  autoflow-cli.py start [--profile <name>]
  autoflow-cli.py stop
  autoflow-cli.py status
  autoflow-cli.py trust <path>
  autoflow-cli.py distrust <path>
  autoflow-cli.py checkpoint [label]
  autoflow-cli.py report
  autoflow-cli.py sprint <profile>
"""

import json
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PLUGIN_ROOT / "autoflow.config.json"
SESSION_FILE = Path.home() / ".autoflow" / "session.json"
LOGS_DIR = Path.home() / ".autoflow" / "logs"


def load_config() -> dict:
    for candidate in [CONFIG_FILE, Path.cwd() / "autoflow.config.json"]:
        if candidate.exists():
            with open(candidate) as f:
                return json.load(f)
    return {}


def load_session() -> dict:
    if SESSION_FILE.exists():
        with open(SESSION_FILE) as f:
            return json.load(f)
    return {
        "active": False,
        "mode": "default",
        "profile": None,
        "trusted_paths_extra": [],
        "checkpoints": [],
        "log": [],
        "started_at": None,
    }


def save_session(session: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)


def cmd_start(args: list[str]) -> None:
    config = load_config()
    session = load_session()

    profile = None
    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            profile = args[idx + 1]

    session["active"] = True
    session["mode"] = config.get("mode", "sprint")
    session["profile"] = profile
    session["started_at"] = datetime.now().isoformat(timespec="seconds")
    session.setdefault("log", [])
    session.setdefault("checkpoints", [])
    session.setdefault("trusted_paths_extra", [])

    save_session(session)

    print("✅  AutoFlow ACTIVE")
    print(f"   Mode      : {session['mode']}")
    print(f"   Profile   : {profile or 'default'}")
    print(f"   Started   : {session['started_at']}")

    effective_paths = config.get("trusted_paths", [])
    if profile:
        profiles = config.get("profiles", {})
        p = profiles.get(profile, {})
        effective_paths = p.get("trusted_paths", effective_paths)

    print(f"   Trusted paths: {', '.join(effective_paths) if effective_paths else '(none)'}")
    print("\n   All operations in trusted paths are auto-approved.")
    print("   Destructive patterns are always hard-blocked.")


def cmd_stop(args: list[str]) -> None:
    session = load_session()
    if not session.get("active"):
        print("AutoFlow was not active.")
        return

    session["active"] = False
    session["stopped_at"] = datetime.now().isoformat(timespec="seconds")

    # Save final session to logs
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = session.get("started_at", datetime.now().isoformat(timespec="seconds")).replace(":", "-")
    log_file = LOGS_DIR / f"session-{ts}.json"
    with open(log_file, "w") as f:
        json.dump(session, f, indent=2)

    save_session(session)

    log_count = len(session.get("log", []))
    cp_count = len(session.get("checkpoints", []))
    print("🛑  AutoFlow STOPPED")
    print(f"   {log_count} actions logged | {cp_count} checkpoints created")
    print(f"   Session saved to: {log_file}")
    print("\n   Run `/autoflow report` to view the session summary.")


def cmd_status(args: list[str]) -> None:
    config = load_config()
    session = load_session()

    if not session.get("active"):
        print("⚪  AutoFlow is INACTIVE")
        print("\n   Run `/autoflow start` to activate autonomous mode.")
        return

    profile = session.get("profile")
    effective_threshold = config.get("risk_threshold", "medium")
    if profile:
        p = config.get("profiles", {}).get(profile, {})
        effective_threshold = p.get("risk_threshold", effective_threshold)

    log = session.get("log", [])
    auto_count = sum(1 for e in log if e["decision"] == "allow")
    notify_count = sum(1 for e in log if e["decision"] == "notify")
    block_count = sum(1 for e in log if e["decision"] == "block")
    cp_count = len(session.get("checkpoints", []))

    print("🟢  AutoFlow is ACTIVE")
    print(f"   Mode            : {session.get('mode', 'sprint')}")
    print(f"   Profile         : {profile or 'default'}")
    print(f"   Risk threshold  : {effective_threshold}")
    print(f"   Started         : {session.get('started_at', 'unknown')}")
    print(f"   Extra trust     : {', '.join(session.get('trusted_paths_extra', [])) or '(none)'}")
    print()
    print(f"   Session log     : {len(log)} entries")
    print(f"     ✅ auto-approved : {auto_count}")
    print(f"     📋 notified      : {notify_count}")
    print(f"     🚫 blocked       : {block_count}")
    print(f"     📌 checkpoints   : {cp_count}")

    if log:
        print("\n   Last 5 actions:")
        for entry in log[-5:]:
            icon = {"allow": "✅", "notify": "📋", "block": "🚫", "checkpoint": "📌"}.get(entry["decision"], "?")
            print(f"     {icon} [{entry['ts']}] {entry['tool']} — {entry['details'][:60]}")


def cmd_trust(args: list[str]) -> None:
    if not args:
        print("Usage: /autoflow trust <path>")
        return
    path = args[0].rstrip("/") + "/"
    session = load_session()
    extra = session.setdefault("trusted_paths_extra", [])
    if path not in extra:
        extra.append(path)
        save_session(session)
        print(f"✅  Added to trusted paths: {path}")
    else:
        print(f"ℹ️   Already trusted: {path}")


def cmd_distrust(args: list[str]) -> None:
    if not args:
        print("Usage: /autoflow distrust <path>")
        return
    path = args[0].rstrip("/") + "/"
    session = load_session()
    extra = session.get("trusted_paths_extra", [])
    if path in extra:
        extra.remove(path)
        save_session(session)
        print(f"🚫  Removed from trusted paths: {path}")
    else:
        print(f"ℹ️   Path was not in extra trusted list: {path}")


def cmd_checkpoint(args: list[str]) -> None:
    label = args[0] if args else "manual"
    checkpoint_script = PLUGIN_ROOT / "scripts" / "checkpoint.sh"
    if not checkpoint_script.exists():
        print("checkpoint.sh not found")
        return
    result = subprocess.run(
        ["bash", str(checkpoint_script), "manual", label],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        tag = result.stdout.strip()
        print(f"📌  Checkpoint created: {tag}")
    else:
        print(f"❌  Checkpoint failed: {result.stderr.strip()}")


def cmd_report(args: list[str]) -> None:
    session = load_session()
    log = session.get("log", [])

    if not log and not session.get("active"):
        # Try to find the last saved session log
        if LOGS_DIR.exists():
            log_files = sorted(LOGS_DIR.glob("session-*.json"))
            if log_files:
                with open(log_files[-1]) as f:
                    session = json.load(f)
                log = session.get("log", [])
                print(f"📄  Showing last saved session: {log_files[-1].name}\n")

    if not log:
        print("No session log available. Start a session with `/autoflow start`.")
        return

    auto_count = sum(1 for e in log if e["decision"] == "allow")
    notify_count = sum(1 for e in log if e["decision"] == "notify")
    block_count = sum(1 for e in log if e["decision"] == "block")
    cp_count = len(session.get("checkpoints", []))

    print("═══════════════════════════════════════════")
    print("  AutoFlow Session Report")
    print("═══════════════════════════════════════════")
    print(f"  Started : {session.get('started_at', 'unknown')}")
    print(f"  Profile : {session.get('profile') or 'default'}")
    print()
    print(f"  ✅ Auto-approved : {auto_count}")
    print(f"  📋 Notified      : {notify_count}")
    print(f"  🚫 Blocked       : {block_count}")
    print(f"  📌 Checkpoints   : {cp_count}")
    print()

    if session.get("checkpoints"):
        print("  Checkpoints:")
        for cp in session["checkpoints"]:
            print(f"    📌 {cp['ts']} — {cp['tag']}")
        print()

    print("  Full action log:")
    for entry in log:
        icon = {"allow": "✅", "notify": "📋", "block": "🚫", "checkpoint": "📌"}.get(entry["decision"], "?")
        print(f"    {icon} {entry['ts']} | {entry['tool']:<16} | {entry['reason']}")

    print("═══════════════════════════════════════════")

    # Save markdown report
    report_path = Path.cwd() / ".autoflow-report.md"
    _save_markdown_report(session, log, report_path)
    print(f"\n  Markdown report saved: {report_path}")


def _save_markdown_report(session: dict, log: list, path: Path) -> None:
    lines = [
        "# AutoFlow Session Report\n",
        f"**Started**: {session.get('started_at', 'unknown')}  ",
        f"**Profile**: {session.get('profile') or 'default'}  ",
        f"**Mode**: {session.get('mode', 'sprint')}  \n",
        "## Summary\n",
        f"| Decision | Count |",
        f"|----------|-------|",
        f"| ✅ Auto-approved | {sum(1 for e in log if e['decision'] == 'allow')} |",
        f"| 📋 Notified | {sum(1 for e in log if e['decision'] == 'notify')} |",
        f"| 🚫 Blocked | {sum(1 for e in log if e['decision'] == 'block')} |",
        f"| 📌 Checkpoints | {len(session.get('checkpoints', []))} |",
        "",
    ]

    if session.get("checkpoints"):
        lines.append("## Checkpoints\n")
        for cp in session["checkpoints"]:
            lines.append(f"- `{cp['tag']}` — {cp['ts']} ({cp['label']})")
        lines.append("")

    lines.append("## Action Log\n")
    lines.append("| Time | Decision | Tool | Details | Reason |")
    lines.append("|------|----------|------|---------|--------|")
    for entry in log:
        icon = {"allow": "✅", "notify": "📋", "block": "🚫", "checkpoint": "📌"}.get(entry["decision"], "?")
        ts = entry["ts"]
        tool = entry["tool"]
        details = entry["details"].replace("|", "\\|")[:60]
        reason = entry["reason"].replace("|", "\\|")[:80]
        lines.append(f"| {ts} | {icon} {entry['decision']} | {tool} | {details} | {reason} |")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def cmd_sprint(args: list[str]) -> None:
    if not args:
        config = load_config()
        profiles = config.get("profiles", {})
        print("Available sprint profiles:")
        for name, profile in profiles.items():
            threshold = profile.get("risk_threshold", config.get("risk_threshold", "medium"))
            paths = profile.get("trusted_paths", config.get("trusted_paths", []))
            print(f"  {name}: threshold={threshold}, paths={', '.join(paths)}")
        print("\nUsage: /autoflow sprint <profile>")
        return

    profile = args[0]
    config = load_config()
    if profile not in config.get("profiles", {}):
        print(f"❌  Unknown profile: {profile}")
        print(f"Available: {', '.join(config.get('profiles', {}).keys())}")
        return

    cmd_start(["--profile", profile])


COMMANDS = {
    "start": cmd_start,
    "stop": cmd_stop,
    "status": cmd_status,
    "trust": cmd_trust,
    "distrust": cmd_distrust,
    "checkpoint": cmd_checkpoint,
    "report": cmd_report,
    "sprint": cmd_sprint,
}


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        print("Usage: autoflow-cli.py <command> [args...]")
        print(f"Commands: {', '.join(COMMANDS)}")
        sys.exit(1)

    cmd = argv[0]
    args = argv[1:]

    handler = COMMANDS.get(cmd)
    if not handler:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(COMMANDS)}")
        sys.exit(1)

    handler(args)


if __name__ == "__main__":
    main()
