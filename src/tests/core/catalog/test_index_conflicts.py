"""Tests for detecting `<dir>.html` vs `<dir>/index.html` conflicts."""

from pathlib import Path

from django_cotton_gallery.core.catalog import find_index_conflicts
from django_cotton_gallery.core.schemas import CatalogConfig, IndexConflict


def _write(root: Path, rel: str, content: str = "x") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


class TestFindIndexConflicts:
    def test_no_conflict_when_only_sibling(self, tmp_path: Path):
        _write(tmp_path, "atoms/button.html")
        assert find_index_conflicts(CatalogConfig(cotton_dir=tmp_path)) == ()

    def test_no_conflict_when_only_index(self, tmp_path: Path):
        _write(tmp_path, "atoms/button/index.html")
        assert find_index_conflicts(CatalogConfig(cotton_dir=tmp_path)) == ()

    def test_reports_conflict_with_winner_and_shadowed(self, tmp_path: Path):
        _write(tmp_path, "atoms/button.html")
        _write(tmp_path, "atoms/button/index.html")
        conflicts = find_index_conflicts(CatalogConfig(cotton_dir=tmp_path))
        assert conflicts == (
            IndexConflict(
                path="atoms/button",
                winner="atoms/button.html",
                shadowed="atoms/button/index.html",
            ),
        )

    def test_top_level_conflict(self, tmp_path: Path):
        _write(tmp_path, "button.html")
        _write(tmp_path, "button/index.html")
        conflicts = find_index_conflicts(CatalogConfig(cotton_dir=tmp_path))
        assert [c.path for c in conflicts] == ["button"]
        assert conflicts[0].winner == "button.html"
        assert conflicts[0].shadowed == "button/index.html"

    def test_multiple_conflicts_sorted_by_path(self, tmp_path: Path):
        for name in ("molecules/card", "atoms/button"):
            _write(tmp_path, f"{name}.html")
            _write(tmp_path, f"{name}/index.html")
        conflicts = find_index_conflicts(CatalogConfig(cotton_dir=tmp_path))
        assert [c.path for c in conflicts] == ["atoms/button", "molecules/card"]

    def test_dotted_dir_name(self, tmp_path: Path):
        _write(tmp_path, "button.v2.html")
        _write(tmp_path, "button.v2/index.html")
        (conflict,) = find_index_conflicts(CatalogConfig(cotton_dir=tmp_path))
        assert conflict.winner == "button.v2.html"

    def test_root_index_is_not_a_conflict(self, tmp_path: Path):
        # `cotton/index.html` is a plain component named "index", not a dir entry.
        _write(tmp_path, "index.html")
        assert find_index_conflicts(CatalogConfig(cotton_dir=tmp_path)) == ()

    def test_excluded_categories_are_ignored(self, tmp_path: Path):
        _write(tmp_path, "molecules/card.html")
        _write(tmp_path, "molecules/card/index.html")
        config = CatalogConfig(cotton_dir=tmp_path, excluded_categories=frozenset({"molecules"}))
        assert find_index_conflicts(config) == ()

    def test_private_folders_are_ignored(self, tmp_path: Path):
        _write(tmp_path, "_private/button.html")
        _write(tmp_path, "_private/button/index.html")
        _write(tmp_path, "atoms/_hidden.html")
        _write(tmp_path, "atoms/_hidden/index.html")
        assert find_index_conflicts(CatalogConfig(cotton_dir=tmp_path)) == ()

    def test_missing_cotton_dir_yields_nothing(self, tmp_path: Path):
        config = CatalogConfig(cotton_dir=tmp_path / "does_not_exist")
        assert find_index_conflicts(config) == ()

    def test_conflict_paths_match_scanned_components(self, tmp_path: Path):
        """Every conflict names a component the catalog actually lists."""
        from django_cotton_gallery.core.catalog import scan

        _write(tmp_path, "atoms/button.html", "{# @description Sibling #}")
        _write(tmp_path, "atoms/button/index.html", "{# @description Index #}")
        config = CatalogConfig(cotton_dir=tmp_path)
        scanned = {c.path: c for c in scan(config)}
        (conflict,) = find_index_conflicts(config)
        assert conflict.path in scanned
        assert scanned[conflict.path].description == "Sibling"
