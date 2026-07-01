"""Tests for schemas — verify immutability, defaults, and computed properties."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from django_cotton_gallery.core.schemas import (
    CatalogConfig,
    Component,
    GalleryAssets,
    ParsedComponent,
    Prop,
    Slot,
)


class TestProp:
    def test_required_fields(self):
        prop = Prop(name="variant", clean_name="variant", type="text")
        assert prop.name == "variant"
        assert prop.clean_name == "variant"
        assert prop.type == "text"

    def test_defaults(self):
        prop = Prop(name="x", clean_name="x", type="text")
        assert prop.options == ()
        assert prop.default == ""
        assert prop.has_default is False
        assert prop.description == ""
        assert prop.required is False
        assert prop.deprecated is None
        assert prop.hidden is False
        assert prop.example == ""

    def test_is_frozen(self):
        prop = Prop(name="x", clean_name="x", type="text")
        with pytest.raises(FrozenInstanceError):
            prop.name = "y"  # type: ignore[misc]

    def test_select_with_options(self):
        prop = Prop(
            name="size",
            clean_name="size",
            type="select",
            options=("sm", "md", "lg"),
            default="md",
            has_default=True,
        )
        assert prop.options == ("sm", "md", "lg")
        assert prop.default == "md"

    def test_boolean_default(self):
        prop = Prop(
            name="loading", clean_name="loading", type="boolean", default=False, has_default=True
        )
        assert prop.default is False


class TestSlot:
    def test_default_slot_has_no_name(self):
        slot = Slot(name=None)
        assert slot.name is None
        assert slot.content == ""
        assert slot.description == ""

    def test_named_slot(self):
        slot = Slot(name="actions", content="<button>Save</button>", description="Action buttons")
        assert slot.name == "actions"

    def test_is_frozen(self):
        slot = Slot(name=None)
        with pytest.raises(FrozenInstanceError):
            slot.content = "mutated"  # type: ignore[misc]


class TestParsedComponent:
    def test_empty_component(self):
        parsed = ParsedComponent()
        assert parsed.props == ()
        assert parsed.slots == ()
        assert parsed.trigger == ""
        assert parsed.description == ""
        assert parsed.accepts_attrs is False

    def test_has_slots_false_when_empty(self):
        assert ParsedComponent().has_slots is False

    def test_has_slots_true_when_populated(self):
        parsed = ParsedComponent(slots=(Slot(name=None),))
        assert parsed.has_slots is True

    def test_is_frozen(self):
        parsed = ParsedComponent()
        with pytest.raises(FrozenInstanceError):
            parsed.trigger = "x"  # type: ignore[misc]


class TestComponent:
    def test_required_fields(self):
        component = Component(
            name="button",
            path="atoms/button",
            tag_path="atoms.button",
            category="atoms",
            subcategory="",
        )
        assert component.name == "button"
        assert component.description == ""
        assert component.source == ""

    def test_nested_path(self):
        component = Component(
            name="button",
            path="atoms/ui/button",
            tag_path="atoms.ui.button",
            category="atoms",
            subcategory="ui",
        )
        assert component.subcategory == "ui"

    def test_is_frozen(self):
        component = Component(name="x", path="x", tag_path="x", category="x", subcategory="")
        with pytest.raises(FrozenInstanceError):
            component.name = "y"  # type: ignore[misc]


class TestGalleryAssets:
    def test_empty_assets(self):
        assets = GalleryAssets()
        assert assets.extra_css == ()
        assert assets.extra_js == ()
        assert assets.dependencies == ()

    def test_populated(self):
        assets = GalleryAssets(
            extra_css=("/static/app.css",),
            extra_js=("/static/app.js",),
        )
        assert assets.extra_css == ("/static/app.css",)
        assert assets.extra_js == ("/static/app.js",)

    def test_is_frozen(self):
        assets = GalleryAssets()
        with pytest.raises(FrozenInstanceError):
            assets.extra_css = ("/x.css",)  # type: ignore[misc]


class TestCatalogConfig:
    def test_minimal(self, tmp_path: Path):
        config = CatalogConfig(cotton_dir=tmp_path)
        assert config.cotton_dir == tmp_path
        assert config.excluded_categories == frozenset()
        assert config.category_order == ()
        assert config.category_sort == "asc"
        assert config.subcategory_order == {}
        assert config.subcategory_sort == "asc"

    def test_full(self, tmp_path: Path):
        config = CatalogConfig(
            cotton_dir=tmp_path,
            excluded_categories=frozenset({"private"}),
            category_order=("atoms", "molecules"),
            category_sort="desc",
            subcategory_order={"atoms": ("ui", "form")},
            subcategory_sort="desc",
        )
        assert "private" in config.excluded_categories
        assert config.category_order == ("atoms", "molecules")
        assert config.subcategory_order["atoms"] == ("ui", "form")

    def test_is_frozen(self, tmp_path: Path):
        config = CatalogConfig(cotton_dir=tmp_path)
        with pytest.raises(FrozenInstanceError):
            config.category_sort = "desc"  # type: ignore[misc]
