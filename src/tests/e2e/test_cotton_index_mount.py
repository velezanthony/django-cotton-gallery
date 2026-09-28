"""E2E tests for the Cotton component index behind the slot intellisense.

Covers the pages that have a slot editor but no component of their own.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

COMPARE = "/django-cotton-gallery/compare/?a=atoms/button&b=atoms/input"
MENU = "[data-cg-slot-editor] [data-cg-intellisense]"
# Added by the highlighter, which binds right before the intellisense. Waiting
# on the textarea alone races the boot.
READY = "[data-cg-slot-textarea].cg-textarea--highlighted"


def _open_cotton_suggestions(page: Page) -> None:
    """Type the prefix that only matches Cotton component tags."""
    page.wait_for_selector(READY)
    editor = page.locator("[data-cg-slot-textarea]").first
    editor.click()
    editor.press("Control+a")
    page.keyboard.type("<c-")


def test_compare_offers_cotton_components(page: Page, live_gallery: str) -> None:
    """A slot editor on the compare page suggests the catalog's components."""
    page.goto(f"{live_gallery}{COMPARE}")

    _open_cotton_suggestions(page)

    # What the menu offers, not whether it is still open — compare's debounced
    # refetch swaps the panel and dismisses the popover a moment later.
    expect(page.locator(MENU).first).to_contain_text("c-atoms.button")


def test_detail_still_offers_components_after_visiting_compare(
    page: Page, live_gallery: str
) -> None:
    """An index computed on compare must not poison the rest of the session."""
    page.goto(f"{live_gallery}{COMPARE}")
    _open_cotton_suggestions(page)

    # The marker proves the click stayed on the SPA path — a reload would reset
    # the cache and hide the regression.
    page.evaluate("() => { window.__cgProbe = 'alive'; }")
    page.locator("[data-cg-sidebar] a[href$='/atoms/button/']").first.click()
    page.wait_for_selector("[data-cg-component-path]")
    assert page.evaluate("() => window.__cgProbe") == "alive", "the click reloaded the page"

    _open_cotton_suggestions(page)

    expect(page.locator(MENU).first).to_contain_text("c-atoms.input")
