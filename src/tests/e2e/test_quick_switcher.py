"""E2E tests for the Ctrl+K quick switcher — SPA navigation, Escape, stacking.

Regression coverage for the power-tools switcher fixes:
  - selecting a result navigates via the SPA interceptor (no full reload)
  - Escape closes the switcher even when focus sits on a hint chip
  - Ctrl+K does not stack the switcher on top of an open editor modal
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_switcher_enter_navigates_via_spa(page: Page, live_gallery: str) -> None:
    """Enter on a result must SPA-swap, not force a full page reload.

    A window global set before navigation survives an SPA swap (same JS
    context, only <main> innerHTML changes) but is wiped by a full reload —
    so its persistence proves navigation.js intercepted the selection.
    """
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    page.evaluate("window.__cgSpaMarker = true")

    page.keyboard.press("Control+k")
    switcher_input = page.locator("[data-cg-switcher-input]")
    expect(switcher_input).to_be_visible()

    switcher_input.fill("but")
    switcher_input.press("Enter")

    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    assert page.evaluate("window.__cgSpaMarker === true"), "expected an SPA swap, got a full reload"
    # Modal closed after selection.
    expect(page.locator("[data-cg-switcher]")).to_be_hidden()


def test_switcher_escape_closes_from_hint_chip(page: Page, live_gallery: str) -> None:
    """Escape closes the switcher even when focus is on a hint chip button."""
    page.goto(f"{live_gallery}/django-cotton-gallery/")

    page.keyboard.press("Control+k")
    expect(page.locator("[data-cg-switcher-input]")).to_be_visible()

    # Move focus off the input onto a hint chip; the old input-only Escape
    # handler would have done nothing here.
    page.locator("[data-cg-hint-insert]").first.focus()
    page.keyboard.press("Escape")

    expect(page.locator("[data-cg-switcher]")).to_be_hidden()


def test_switcher_does_not_stack_on_editor_modal(page: Page, live_gallery: str) -> None:
    """Ctrl+K is a no-op while the editor modal is open (no stacked modals)."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")

    page.click(".cg-control--attrs [data-cg-editor-maximize]")
    expect(page.locator("[data-cg-editor-modal]")).not_to_have_attribute("hidden", "")

    page.keyboard.press("Control+k")

    # Switcher stays closed; the editor modal remains the only open modal.
    expect(page.locator("[data-cg-switcher]")).to_be_hidden()
    expect(page.locator("[data-cg-editor-modal]")).not_to_have_attribute("hidden", "")
