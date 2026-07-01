"""Tests for the catalog scanner."""

from pathlib import Path

from django_cotton_gallery.core.catalog.scanner import (
    group_by_category,
    scan,
    signature,
)
from django_cotton_gallery.core.schemas import CatalogConfig, Component


class TestScan:
    def test_yields_components_from_tree(self, basic_config):
        components = list(scan(basic_config))
        names = sorted(c.name for c in components)
        # `loose` is a top-level component (cotton/loose.html) — it now
        # qualifies for the catalog because categories are optional.
        assert names == ["badge", "button", "card", "input", "loose"]

    def test_skips_private_folders(self, basic_config):
        components = list(scan(basic_config))
        assert all("_private" not in c.path for c in components)

    def test_skips_private_files(self, basic_config):
        components = list(scan(basic_config))
        assert all(c.name != "_internal" for c in components)

    def test_loose_top_level_files_are_uncategorized(self, basic_config):
        """Top-level `<file>.html` is included with empty category — categories
        are an organizational choice, not a filesystem requirement.
        """
        components = {c.name: c for c in scan(basic_config)}
        assert components["loose"].category == ""
        assert components["loose"].subcategory == ""
        assert components["loose"].path == "loose"

    def test_extracts_description(self, basic_config):
        components = {c.name: c for c in scan(basic_config)}
        assert components["button"].description == "Button"

    def test_path_and_tag_path(self, basic_config):
        components = {c.name: c for c in scan(basic_config)}
        assert components["button"].path == "atoms/button"
        assert components["button"].tag_path == "atoms.button"
        assert components["badge"].path == "atoms/ui/badge"
        assert components["badge"].tag_path == "atoms.ui.badge"

    def test_subcategory_for_nested(self, basic_config):
        components = {c.name: c for c in scan(basic_config)}
        assert components["badge"].subcategory == "ui"
        assert components["button"].subcategory == ""

    def test_excluded_categories(self, cotton_tree: Path):
        config = CatalogConfig(cotton_dir=cotton_tree, excluded_categories=frozenset({"molecules"}))
        names = [c.name for c in scan(config)]
        assert "card" not in names
        assert "button" in names

    def test_missing_cotton_dir_yields_nothing(self, tmp_path: Path):
        config = CatalogConfig(cotton_dir=tmp_path / "does_not_exist")
        assert list(scan(config)) == []


class TestIndexFilePattern:
    """`<dir>/index.html` is treated as the canonical entry point for a
    component named after `<dir>`. Mirrors cotton's loader behaviour.
    """

    def test_index_file_uses_parent_dir_name(self, tmp_path: Path):
        cotton = tmp_path / "cotton"
        (cotton / "atoms" / "button").mkdir(parents=True)
        (cotton / "atoms" / "button" / "index.html").write_text(
            "{# @description Button via index #}\n<button>{{ slot }}</button>"
        )
        config = CatalogConfig(cotton_dir=cotton)
        components = list(scan(config))
        assert len(components) == 1
        assert components[0].name == "button"
        assert components[0].path == "atoms/button"
        assert components[0].tag_path == "atoms.button"
        assert components[0].description == "Button via index"

    def test_index_pattern_with_subcategory(self, tmp_path: Path):
        cotton = tmp_path / "cotton"
        (cotton / "atoms" / "ui" / "alert").mkdir(parents=True)
        (cotton / "atoms" / "ui" / "alert" / "index.html").write_text(
            "{# @description Alert #}\n<div>{{ slot }}</div>"
        )
        config = CatalogConfig(cotton_dir=cotton)
        components = list(scan(config))
        assert len(components) == 1
        assert components[0].name == "alert"
        assert components[0].path == "atoms/ui/alert"
        assert components[0].tag_path == "atoms.ui.alert"
        assert components[0].subcategory == "ui"

    def test_sibling_html_wins_over_index(self, tmp_path: Path):
        """When both `<dir>.html` and `<dir>/index.html` exist, the sibling
        wins (matches cotton's resolution order: primary path first).
        """
        cotton = tmp_path / "cotton"
        (cotton / "atoms" / "button").mkdir(parents=True)
        (cotton / "atoms" / "button.html").write_text(
            "{# @description Sibling wins #}\n<button>{{ slot }}</button>"
        )
        (cotton / "atoms" / "button" / "index.html").write_text(
            "{# @description Index file #}\n<button>{{ slot }}</button>"
        )
        config = CatalogConfig(cotton_dir=cotton)
        components = list(scan(config))
        # Only one component yielded (the sibling), index dropped.
        assert len(components) == 1
        assert components[0].description == "Sibling wins"
        assert components[0].path == "atoms/button"

    def test_mix_of_index_and_regular_components(self, tmp_path: Path):
        cotton = tmp_path / "cotton"
        # Regular: cotton/atoms/badge.html
        (cotton / "atoms").mkdir(parents=True)
        (cotton / "atoms" / "badge.html").write_text(
            "{# @description Badge #}\n<span>{{ slot }}</span>"
        )
        # Index pattern: cotton/atoms/button/index.html
        (cotton / "atoms" / "button").mkdir()
        (cotton / "atoms" / "button" / "index.html").write_text(
            "{# @description Button #}\n<button>{{ slot }}</button>"
        )
        config = CatalogConfig(cotton_dir=cotton)
        components = sorted(scan(config), key=lambda c: c.name)
        assert [c.name for c in components] == ["badge", "button"]
        assert [c.path for c in components] == ["atoms/badge", "atoms/button"]


class TestUncategorizedComponents:
    """Components at the root of cotton/ have no category folder.
    Categories are an organizational choice, not a filesystem requirement.
    """

    def test_loose_root_html_yields_component(self, tmp_path: Path):
        cotton = tmp_path / "cotton"
        cotton.mkdir()
        (cotton / "button.html").write_text(
            "{# @description Loose button #}\n<button>{{ slot }}</button>"
        )
        config = CatalogConfig(cotton_dir=cotton)
        components = list(scan(config))
        assert len(components) == 1
        c = components[0]
        assert c.name == "button"
        assert c.path == "button"
        assert c.tag_path == "button"
        assert c.category == ""
        assert c.subcategory == ""

    def test_loose_index_pattern_yields_component(self, tmp_path: Path):
        """`cotton/button/index.html` (no category folder above) is also valid."""
        cotton = tmp_path / "cotton"
        (cotton / "button").mkdir(parents=True)
        (cotton / "button" / "index.html").write_text(
            "{# @description Loose button via index #}\n<button>{{ slot }}</button>"
        )
        config = CatalogConfig(cotton_dir=cotton)
        components = list(scan(config))
        assert len(components) == 1
        c = components[0]
        assert c.name == "button"
        assert c.path == "button"
        assert c.tag_path == "button"
        assert c.category == ""

    def test_mix_categorized_and_uncategorized(self, tmp_path: Path):
        cotton = tmp_path / "cotton"
        (cotton / "atoms").mkdir(parents=True)
        (cotton / "atoms" / "button.html").write_text("<button/>")
        (cotton / "loose.html").write_text("<div/>")
        config = CatalogConfig(cotton_dir=cotton)
        components = sorted(scan(config), key=lambda c: c.name)
        names = [c.name for c in components]
        cats = {c.name: c.category for c in components}
        assert "button" in names and "loose" in names
        assert cats["button"] == "atoms"
        assert cats["loose"] == ""


class TestSignature:
    def test_signature_changes_on_edit(self, basic_config, cotton_tree: Path):
        sig_before = signature(basic_config)
        button = cotton_tree / "atoms" / "button.html"
        button.write_text("{# @description Edited #}\n")
        # Touch mtime forward to ensure detection on fast filesystems.
        import os

        st = button.stat()
        os.utime(button, (st.st_atime, st.st_mtime + 5))
        sig_after = signature(basic_config)
        assert sig_after != sig_before

    def test_signature_changes_on_addition(self, basic_config, cotton_tree: Path):
        sig_before = signature(basic_config)
        (cotton_tree / "atoms" / "new.html").write_text("{# @description New #}")
        sig_after = signature(basic_config)
        assert sig_after[0] == sig_before[0] + 1

    def test_signature_changes_on_deletion(self, basic_config, cotton_tree: Path):
        sig_before = signature(basic_config)
        (cotton_tree / "atoms" / "input.html").unlink()
        sig_after = signature(basic_config)
        assert sig_after[0] == sig_before[0] - 1

    def test_signature_ignores_excluded(self, cotton_tree: Path):
        excluded = CatalogConfig(
            cotton_dir=cotton_tree, excluded_categories=frozenset({"molecules"})
        )
        unrestricted = CatalogConfig(cotton_dir=cotton_tree)
        assert signature(excluded)[0] < signature(unrestricted)[0]

    def test_signature_for_missing_dir(self, tmp_path: Path):
        config = CatalogConfig(cotton_dir=tmp_path / "missing")
        assert signature(config) == (0, 0.0)


class TestGroupByCategory:
    def test_groups_flat_components(self):
        components = [
            Component(
                name="a", path="atoms/a", tag_path="atoms.a", category="atoms", subcategory=""
            ),
            Component(
                name="b", path="atoms/b", tag_path="atoms.b", category="atoms", subcategory=""
            ),
            Component(
                name="c",
                path="molecules/c",
                tag_path="molecules.c",
                category="molecules",
                subcategory="",
            ),
        ]
        grouped = group_by_category(components)
        assert set(grouped.keys()) == {"atoms", "molecules"}
        assert len(grouped["atoms"][""]) == 2

    def test_groups_with_subcategory(self):
        components = [
            Component(
                name="x",
                path="atoms/ui/x",
                tag_path="atoms.ui.x",
                category="atoms",
                subcategory="ui",
            ),
            Component(
                name="y", path="atoms/y", tag_path="atoms.y", category="atoms", subcategory=""
            ),
        ]
        grouped = group_by_category(components)
        assert set(grouped["atoms"].keys()) == {"ui", ""}

    def test_empty_input(self):
        assert group_by_category([]) == {}
