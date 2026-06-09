#!/usr/bin/env python3
"""Install claude-orchestrator for Claude Code and Hermes Agent."""
import shutil
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.resolve()
SCRIPT = REPO_DIR / "claude_orchestrator.py"
TARGET_HERMES = Path.home() / ".hermes" / "skills" / "claude-orchestrator" / "claude_orchestrator.py"
TARGET_CC = Path.home() / ".claude" / "skills" / "claude-orchestrator" / "claude_orchestrator.py"
SKILL_MD = REPO_DIR / "SKILL.md"

def install():
    if not SCRIPT.exists():
        print("ERROR: claude_orchestrator.py not found next to this script.")
        sys.exit(1)

    TARGET_HERMES.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT, TARGET_HERMES)
    print(f"Installed for Hermes Agent: {TARGET_HERMES}")

    TARGET_CC.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT, TARGET_CC)
    if SKILL_MD.exists():
        shutil.copy2(SKILL_MD, TARGET_CC.parent / "SKILL.md")
    print(f"Installed for Claude Code: {TARGET_CC}")

    print("\nDone. Restart Claude Code to pick up the skill.")

if __name__ == "__main__":
    install()
