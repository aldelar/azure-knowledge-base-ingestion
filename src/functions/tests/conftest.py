"""Shared pytest fixtures for function tests."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory (repo root)."""
    # tests/ is at src/functions/tests/, so go up 3 levels
    return Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture
def staging_path(project_root: Path) -> Path:
    """Return the path to kb/staging/."""
    return project_root / "kb" / "staging"


@pytest.fixture
def serving_path(project_root: Path) -> Path:
    """Return the path to kb/serving/."""
    return project_root / "kb" / "serving"


@pytest.fixture
def sample_article_ids(staging_path: Path) -> list[str]:
    """Return list of article IDs available in kb/staging/."""
    if not staging_path.exists():
        pytest.skip("kb/staging/ not found")
    return [d.name for d in staging_path.iterdir() if d.is_dir()]
