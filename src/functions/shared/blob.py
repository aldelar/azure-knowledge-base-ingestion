"""Blob / file I/O helpers.

For local mode (Epic 1): simple file system read/write wrappers.
For Azure mode (future): Azure Blob Storage SDK calls.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def read_text(path: Path) -> str:
    """Read a text file and return its contents."""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    """Write text content to a file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_file(src: Path, dest: Path) -> None:
    """Copy a file, creating the destination directory if needed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def list_files(directory: Path, pattern: str = "*") -> list[Path]:
    """List files in a directory matching a glob pattern."""
    if not directory.exists():
        return []
    return sorted(f for f in directory.glob(pattern) if f.is_file())

