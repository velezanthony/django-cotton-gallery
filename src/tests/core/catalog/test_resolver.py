"""Tests for component path resolution."""

from pathlib import Path

import pytest

from django_cotton_gallery.core.catalog.resolver import ComponentNotFound, resolve
from django_cotton_gallery.core.path_safety import UnsafePath


class TestResolve:
    def test_existing_flat_component(self, cotton_tree: Path):
        file, tag = resolve(cotton_tree, "atoms/button")
        assert file == cotton_tree / "atoms" / "button.html"
        assert tag == "atoms.button"

    def test_existing_nested_component(self, cotton_tree: Path):
        file, tag = resolve(cotton_tree, "atoms/ui/badge")
        assert file == cotton_tree / "atoms" / "ui" / "badge.html"
        assert tag == "atoms.ui.badge"

    def test_missing_component_raises(self, cotton_tree: Path):
        with pytest.raises(ComponentNotFound):
            resolve(cotton_tree, "atoms/does-not-exist")

    @pytest.mark.parametrize("bad", ["atoms/..", "atoms/.", "../atoms/button", "atoms/_private"])
    def test_traversal_attempts_rejected(self, cotton_tree: Path, bad: str):
        with pytest.raises(UnsafePath):
            resolve(cotton_tree, bad)

    def test_backslash_in_path_rejected(self, cotton_tree: Path):
        with pytest.raises(UnsafePath):
            resolve(cotton_tree, "atoms\\button")

    def test_null_byte_in_path_rejected(self, cotton_tree: Path):
        with pytest.raises(UnsafePath):
            resolve(cotton_tree, "atoms/bu\x00tton")
