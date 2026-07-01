"""Unified file reading with encoding fallback.

Pure — no Django imports. Used everywhere a component source must be loaded.
"""

from __future__ import annotations

from pathlib import Path


def read_text(path: Path) -> str:
    """Read `path` as text. UTF-8 first, falls back to cp1252 for legacy files."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1252")
