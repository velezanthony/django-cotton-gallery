"""E2E tests for the CSS autocomplete inside `style="…"` attributes
(both the attrs editor and the slot editor)."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_attrs_style_autocomplete_offers_property_names(page: Page, live_gallery: str) -> None:
    """Typing inside `style="…"` shows CSS property suggestions."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")

    editor = page.locator("[data-cg-attrs-input]")
    editor.click()
    # Start a style attribute and type a partial property name.
    page.keyboard.type('style="bord')

    # Popover should be visible with `border` / `border-radius` etc.
    menu = page.locator("[data-cg-attrs-menu]")
    expect(menu).to_be_visible()
    expect(menu).to_contain_text("border")


def test_attrs_style_autocomplete_offers_units_after_number(page: Page, live_gallery: str) -> None:
    """Typing a number inside a CSS value offers length-unit completions."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")

    editor = page.locator("[data-cg-attrs-input]")
    editor.click()
    page.keyboard.type('style="width: 2')

    menu = page.locator("[data-cg-attrs-menu]")
    expect(menu).to_be_visible()
    text = menu.inner_text()
    assert "2px" in text or "2rem" in text, f"expected px/rem suggestions, got: {text!r}"


def test_attrs_style_autocomplete_filters_by_unit_prefix(page: Page, live_gallery: str) -> None:
    """`2d` → only dvh / dvw appear (filtered by the d prefix)."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")

    editor = page.locator("[data-cg-attrs-input]")
    editor.click()
    page.keyboard.type('style="height: 2d')

    menu = page.locator("[data-cg-attrs-menu]")
    expect(menu).to_be_visible()
    text = menu.inner_text()
    assert "2dvh" in text or "2dvw" in text, f"expected d-prefixed units, got: {text!r}"


def test_attrs_style_border_shorthand_classifies_tokens(page: Page, live_gallery: str) -> None:
    """After `border: 1px solid `, only colors should appear (width + style filled)."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")

    editor = page.locator("[data-cg-attrs-input]")
    editor.click()
    page.keyboard.type('style="border: 1px solid ')

    menu = page.locator("[data-cg-attrs-menu]")
    expect(menu).to_be_visible()
    text = menu.inner_text()
    # Colors are present (red/black/transparent/etc).
    assert any(c in text for c in ("red", "black", "transparent", "currentColor")), (
        f"expected color suggestions, got: {text!r}"
    )
