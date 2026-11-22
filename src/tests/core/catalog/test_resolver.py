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


class TestResolveIndexFallback:
    """`<dir>/index.html` serves component `<dir>` when `<dir>.html` is absent.

    Mirrors Cotton's loader and the scanner: the sibling file wins when both
    exist, so the detail page shows the same file Cotton renders.
    """

    def test_sibling_only(self, tmp_path: Path):
        (tmp_path / "atoms").mkdir()
        (tmp_path / "atoms" / "button.html").write_text("sibling")
        file, tag = resolve(tmp_path, "atoms/button")
        assert file == tmp_path / "atoms" / "button.html"
        assert tag == "atoms.button"

    def test_index_only(self, tmp_path: Path):
        (tmp_path / "atoms" / "button").mkdir(parents=True)
        (tmp_path / "atoms" / "button" / "index.html").write_text("index")
        file, tag = resolve(tmp_path, "atoms/button")
        assert file == tmp_path / "atoms" / "button" / "index.html"
        assert tag == "atoms.button"

    def test_top_level_index_only(self, tmp_path: Path):
        (tmp_path / "button").mkdir()
        (tmp_path / "button" / "index.html").write_text("index")
        file, tag = resolve(tmp_path, "button")
        assert file == tmp_path / "button" / "index.html"
        assert tag == "button"

    def test_both_sibling_wins(self, tmp_path: Path):
        (tmp_path / "button").mkdir()
        (tmp_path / "button.html").write_text("sibling")
        (tmp_path / "button" / "index.html").write_text("index")
        file, _ = resolve(tmp_path, "button")
        assert file == tmp_path / "button.html"

    def test_neither_raises(self, tmp_path: Path):
        (tmp_path / "button").mkdir()
        with pytest.raises(ComponentNotFound):
            resolve(tmp_path, "button")

    def test_dir_without_index_raises(self, tmp_path: Path):
        (tmp_path / "button").mkdir()
        (tmp_path / "button" / "other.html").write_text("x")
        with pytest.raises(ComponentNotFound):
            resolve(tmp_path, "button")

    @pytest.mark.parametrize("bad", ["../button", "button/..", "_private"])
    def test_path_safety_still_enforced(self, tmp_path: Path, bad: str):
        (tmp_path / "_private").mkdir()
        (tmp_path / "_private" / "index.html").write_text("x")
        with pytest.raises(UnsafePath):
            resolve(tmp_path, bad)

    def test_index_symlink_escaping_root_rejected(self, tmp_path: Path):
        root = tmp_path / "cotton"
        (root / "button").mkdir(parents=True)
        outside = tmp_path / "outside.html"
        outside.write_text("secret")
        (root / "button" / "index.html").symlink_to(outside)
        with pytest.raises(UnsafePath):
            resolve(root, "button")
