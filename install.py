#!/usr/bin/env python3
"""Install cc-workflows for Claude Code and Hermes Agent."""
import shutil
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.resolve()
SKILLS_DIR = REPO_DIR / "skills"
MAIN_SKILL = SKILLS_DIR / "cc-workflows"
SCRIPT = MAIN_SKILL / "claude_orchestrator.py"
SKILL_MD = MAIN_SKILL / "SKILL.md"
TARGET_HERMES = Path.home() / ".hermes" / "skills" / "cc-workflows"
TARGET_CC = Path.home() / ".claude" / "skills" / "cc-workflows"


def install_skill(src: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for fname in ["SKILL.md", "claude_orchestrator.py"]:
        src_file = src / fname
        if src_file.exists():
            shutil.copy2(src_file, dest / fname)
    # copy references if present
    refs = src / "references"
    if refs.exists():
        dst_refs = dest / "references"
        if dst_refs.exists():
            shutil.rmtree(dst_refs)
        shutil.copytree(refs, dst_refs)


def install():
    if not SCRIPT.exists():
        print(f"ERROR: {SCRIPT} not found.")
        sys.exit(1)

    install_skill(MAIN_SKILL, TARGET_HERMES)
    print(f"Installed for Hermes Agent: {TARGET_HERMES}")

    install_skill(MAIN_SKILL, TARGET_CC)
    print(f"Installed for Claude Code: {TARGET_CC}")

    # Also install individual mode skills into both targets
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name in ("cc-workflows", "__pycache__"):
            continue
        if not (skill_dir / "SKILL.md").exists():
            continue

        cc_dest = TARGET_CC / skill_dir.name
        hermes_dest = TARGET_HERMES / skill_dir.name
        install_skill(skill_dir, cc_dest)
        install_skill(skill_dir, hermes_dest)
        print(f"  + {skill_dir.name}")

    print("\nDone. Restart Claude Code to pick up skills.")


if __name__ == "__main__":
    install()
