"""Shared fixtures for catalog tests — builds a temp cotton/ tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from django_cotton_gallery.core.schemas import CatalogConfig


@pytest.fixture
def cotton_tree(tmp_path: Path) -> Path:
    """A representative cotton/ directory layout with mixed nesting and private files."""
    root = tmp_path / "cotton"
    root.mkdir()

    (root / "atoms").mkdir()
    (root / "atoms" / "button.html").write_text("{# @description Button #}")
    (root / "atoms" / "input.html").write_text("{# @description Input #}")

    (root / "atoms" / "ui").mkdir()
    (root / "atoms" / "ui" / "badge.html").write_text("{# @description Badge #}")

    (root / "molecules").mkdir()
    (root / "molecules" / "card.html").write_text("{# @description Card #}")

    # Excluded: top-level file (no category)
    (root / "loose.html").write_text("loose")

    # Excluded: private folder
    (root / "_private").mkdir()
    (root / "_private" / "secret.html").write_text("secret")

    # Excluded: private file inside category
    (root / "atoms" / "_internal.html").write_text("internal")

    return root


@pytest.fixture
def basic_config(cotton_tree: Path) -> CatalogConfig:
    return CatalogConfig(cotton_dir=cotton_tree)
