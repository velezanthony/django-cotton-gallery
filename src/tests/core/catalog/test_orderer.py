"""Tests for catalog ordering."""

from pathlib import Path

from django_cotton_gallery.core.catalog.orderer import order_catalog
from django_cotton_gallery.core.schemas import CatalogConfig, Component


def _make(name: str, category: str, subcategory: str = "") -> Component:
    return Component(
        name=name,
        path=f"{category}/{subcategory}/{name}".strip("/"),
        tag_path=f"{category}.{subcategory}.{name}".strip("."),
        category=category,
        subcategory=subcategory,
    )


def _raw():
    return {
        "molecules": {"": [_make("card", "molecules")]},
        "atoms": {
            "ui": [_make("badge", "atoms", "ui")],
            "": [_make("button", "atoms"), _make("input", "atoms")],
        },
        "organisms": {"": [_make("nav", "organisms")]},
    }


class TestOrderCatalog:
    def test_default_alphabetical_asc(self, tmp_path: Path):
        config = CatalogConfig(cotton_dir=tmp_path)
        result = order_catalog(_raw(), config)
        assert list(result.keys()) == ["atoms", "molecules", "organisms"]

    def test_descending_sort(self, tmp_path: Path):
        config = CatalogConfig(cotton_dir=tmp_path, category_sort="desc")
        result = order_catalog(_raw(), config)
        assert list(result.keys()) == ["organisms", "molecules", "atoms"]

    def test_manual_category_order_overrides_sort(self, tmp_path: Path):
        config = CatalogConfig(
            cotton_dir=tmp_path,
            category_order=("molecules", "atoms"),
        )
        result = order_catalog(_raw(), config)
        assert list(result.keys())[:2] == ["molecules", "atoms"]
        assert "organisms" in list(result.keys())[2:]

    def test_unknown_category_in_manual_prefix_is_skipped(self, tmp_path: Path):
        config = CatalogConfig(
            cotton_dir=tmp_path,
            category_order=("does-not-exist", "atoms"),
        )
        result = order_catalog(_raw(), config)
        assert next(iter(result.keys())) == "atoms"

    def test_subcategory_order(self, tmp_path: Path):
        raw = {
            "atoms": {
                "ui": [_make("a", "atoms", "ui")],
                "form": [_make("b", "atoms", "form")],
                "": [_make("c", "atoms")],
            },
        }
        config = CatalogConfig(
            cotton_dir=tmp_path,
            subcategory_order={"atoms": ("ui", "form", "")},
        )
        result = order_catalog(raw, config)
        assert list(result["atoms"].keys()) == ["ui", "form", ""]

    def test_empty_input(self, tmp_path: Path):
        config = CatalogConfig(cotton_dir=tmp_path)
        assert order_catalog({}, config) == {}

    def test_uncategorized_bucket_sorts_last(self, tmp_path: Path):
        """The empty-string category (loose components at cotton/ root)
        always appears AFTER named categories regardless of sort
        direction or manual ordering.
        """
        raw = {
            "atoms": {"": [_make("a", "atoms")]},
            "molecules": {"": [_make("b", "molecules")]},
            "": {"": [_make("loose", "")]},
        }
        config = CatalogConfig(cotton_dir=tmp_path)
        result = order_catalog(raw, config)
        keys = list(result.keys())
        assert keys[-1] == ""
        assert "atoms" in keys[:-1]
        assert "molecules" in keys[:-1]

    def test_uncategorized_after_manual_prefix(self, tmp_path: Path):
        raw = {
            "atoms": {"": [_make("a", "atoms")]},
            "organisms": {"": [_make("o", "organisms")]},
            "": {"": [_make("loose", "")]},
        }
        config = CatalogConfig(
            cotton_dir=tmp_path,
            category_order=("organisms", "atoms"),
        )
        result = order_catalog(raw, config)
        # Manual prefix order respected, uncategorized at the end.
        assert list(result.keys()) == ["organisms", "atoms", ""]
