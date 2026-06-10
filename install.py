#!/usr/bin/env python3
"""Install cc-workflows for Claude Code, Hermes Agent, and optionally a project directory.

Usage:
  python3 install.py                    # Install to Hermes + Claude Code global
  python3 install.py --project /path    # Also install to project .claude/skills/
  python3 install.py --dry-run          # Preview what would be installed
"""
import shutil
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.resolve()
SKILLS_DIR = REPO_DIR / "skills"
MAIN_SKILL = SKILLS_DIR / "cc-workflows"
SCRIPT = MAIN_SKILL / "cc_workflows.py"
SKILL_MD = MAIN_SKILL / "SKILL.md"
TARGET_HERMES = Path.home() / ".hermes" / "skills" / "cc-workflows"
TARGET_CC = Path.home() / ".claude" / "skills" / "cc-workflows"


def install_skill(src: Path, dest: Path, dry_run: bool = False):
    if dry_run:
        print(f"  [dry-run] Would install: {src.name} → {dest}")
        return
    dest.mkdir(parents=True, exist_ok=True)
    for fname in ["SKILL.md", "cc_workflows.py"]:
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


def parse_args():
    """Parse --project and --dry-run flags from sys.argv."""
    project_path = None
    dry_run = False
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--project" and i + 1 < len(sys.argv):
            project_path = Path(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--dry-run":
            dry_run = True
            i += 1
        else:
            i += 1
    return project_path, dry_run


def install():
    project_path, dry_run = parse_args()

    if not SCRIPT.exists():
        print(f"ERROR: {SCRIPT} not found.")
        sys.exit(1)

    if dry_run:
        print("🔍 Dry-run mode: showing what would be installed\n")

    # 1. Hermes Agent
    install_skill(MAIN_SKILL, TARGET_HERMES, dry_run)
    print(f"Installed for Hermes Agent: {TARGET_HERMES}")

    # 2. Claude Code global
    install_skill(MAIN_SKILL, TARGET_CC, dry_run)
    print(f"Installed for Claude Code: {TARGET_CC}")

    # 3. Individual mode skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name in ("cc-workflows", "__pycache__"):
            continue
        if not (skill_dir / "SKILL.md").exists():
            continue

        cc_dest = TARGET_CC / skill_dir.name
        hermes_dest = TARGET_HERMES / skill_dir.name
        install_skill(skill_dir, cc_dest, dry_run)
        install_skill(skill_dir, hermes_dest, dry_run)
        print(f"  + {skill_dir.name}")

    # 4. Project-level (optional)
    if project_path:
        target_project = project_path / ".claude" / "skills" / "cc-workflows"
        install_skill(MAIN_SKILL, target_project, dry_run)
        print(f"Installed for project: {target_project}")

        # Also copy the root-level script for convenience
        root_script = REPO_DIR / "cc_workflows.py"
        if root_script.exists():
            if not dry_run:
                shutil.copy2(root_script, project_path / "cc_workflows.py")
            print(f"  + cc_workflows.py → {project_path}")

    if dry_run:
        print("\n(dry-run: no files were actually copied)")
    else:
        print("\nDone. Restart Claude Code to pick up skills.")


if __name__ == "__main__":
    install()
