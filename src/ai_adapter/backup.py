"""Shared backup utilities for doctor --fix and optimize --apply.

Provides a unified snapshot mechanism so that both commands back up the same
categories (config, skills, instructions) before making changes.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from ai_adapter.config import add_to_gitignore


def get_backup_dir() -> Path:
    """Return the backup directory path (git-ignored)."""
    from ai_adapter import config as _cfg

    return _cfg.AI_ADAPTER_DIR / "backups"


def create_snapshot(label: str) -> Path | None:
    """Create a snapshot of the store before applying fixes.

    Backs up config.json, skills/, and instructions/ (the full mutable state).

    Returns the snapshot directory, or None if the store doesn't exist.
    """
    from ai_adapter import config as _cfg

    adapter_dir = _cfg.AI_ADAPTER_DIR
    if not adapter_dir.exists():
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = get_backup_dir() / f"{timestamp}_{label}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Copy config.json if it exists.
    config_path = adapter_dir / "config.json"
    if config_path.is_file():
        shutil.copy2(config_path, backup_dir / "config.json")

    # Copy skills directory.
    skills_dir = adapter_dir / "skills"
    if skills_dir.is_dir():
        shutil.copytree(skills_dir, backup_dir / "skills", dirs_exist_ok=True)

    # Copy instructions directory.
    instructions_dir = adapter_dir / "instructions"
    if instructions_dir.is_dir():
        shutil.copytree(instructions_dir, backup_dir / "instructions", dirs_exist_ok=True)

    return backup_dir


def ensure_backups_gitignored() -> None:
    """Add backups/ to .gitignore so backup files are never committed."""
    backups_dir = get_backup_dir()
    backups_dir.mkdir(parents=True, exist_ok=True)
    add_to_gitignore(backups_dir)
