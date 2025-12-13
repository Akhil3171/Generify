from __future__ import annotations

from pathlib import Path


def _get_data_dir() -> Path:
    """Return the Data directory path relative to the project root."""
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "Data"


def products_db_path() -> str:
    """Return the path to products.db (Orange Book data)."""
    return str(_get_data_dir() / "products.db")


def medicare_db_path() -> str:
    """Return the path to medicare.db (CMS Part D data)."""
    return str(_get_data_dir() / "medicare.db")

