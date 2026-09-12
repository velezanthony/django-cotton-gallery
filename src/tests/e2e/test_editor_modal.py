"""E2E tests for the editor maximize modal — open / edit / format / reset / close."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from ._frames import stage_frame


def test_modal_opens_with_maximize_button(page: Page, live_gallery: str) -> None:
    """Clicking the maximize button moves the editor into the modal panel."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")

    # Modal starts hidden.
    expect(page.locator("[data-cg-editor-modal]")).to_have_attribute("hidden", "")

    # Click the maximize button on the attrs control.
    page.click(".cg-control--attrs [data-cg-editor-maximize]")

    # Modal becomes visible and contains the contenteditable.
    expect(page.locator("[data-cg-editor-modal]")).not_to_have_attribute("hidden", "")
    expect(page.locator("[data-cg-editor-modal-slot] [data-cg-attrs-input]")).to_be_visible()


def test_modal_close_button_restores_editor(page: Page, live_gallery: str) -> None:
    """The x button moves the editor back to its original placeholder."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")

    page.click(".cg-control--attrs [data-cg-editor-maximize]")
    expect(page.locator("[data-cg-editor-modal-slot] [data-cg-attrs-input]")).to_be_visible()

    page.click("button[data-cg-editor-modal-close]")
    expect(page.locator("[data-cg-editor-modal]")).to_have_attribute("hidden", "")
    # Editor is back in the controls panel, NOT in the modal slot.
    expect(page.locator(".cg-control--attrs [data-cg-attrs-input]")).to_be_visible()


def test_modal_escape_closes(page: Page, live_gallery: str) -> None:
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")
    page.click(".cg-control--attrs [data-cg-editor-maximize]")
    expect(page.locator("[data-cg-editor-modal]")).not_to_have_attribute("hidden", "")

    page.keyboard.press("Escape")
    expect(page.locator("[data-cg-editor-modal]")).to_have_attribute("hidden", "")


def test_modal_stats_update_on_input(page: Page, live_gallery: str) -> None:
    """Footer stats reflect chars/lines as the user types."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")
    page.click(".cg-control--attrs [data-cg-editor-maximize]")

    editable = page.locator("[data-cg-editor-modal-slot] [data-cg-attrs-input]")
    editable.fill('class="btn"')

    chars = page.locator("[data-cg-editor-modal-chars]")
    expect(chars).to_have_text("11")


def test_modal_reset_restores_initial_value(page: Page, live_gallery: str) -> None:
    """Reset clears edits made inside the modal back to the value at open time."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")

    # Pre-set a value before opening the modal so Reset has something to restore TO.
    initial = 'class="initial"'
    page.evaluate(
        '(value) => { const el = document.querySelector("[data-cg-attrs-input]"); '
        'el.textContent = value; el.dispatchEvent(new Event("input", {bubbles: true})); }',
        initial,
    )
    page.click(".cg-control--attrs [data-cg-editor-maximize]")

    # Edit inside the modal.
    editable = page.locator("[data-cg-editor-modal-slot] [data-cg-attrs-input]")
    editable.fill("disabled")

    # Reset → editor goes back to the initial value.
    page.click("[data-cg-editor-modal-reset]")
    expect(editable).to_have_text(initial)


def test_modal_format_button_hidden_for_attrs(page: Page, live_gallery: str) -> None:
    """attrs has no formatter; the modal's Format button hides itself there."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")
    page.click(".cg-control--attrs [data-cg-editor-maximize]")
    expect(page.locator("[data-cg-editor-modal-format]")).to_be_hidden()


def test_modal_edit_refreshes_preview_on_close(page: Page, live_gallery: str) -> None:
    """Editing inside the modal and closing must update the live preview.

    The modal moves the editor OUT of the controls form, so its input events
    don't reach the form-delegated preview debounce — close() has to flush the
    change or the edit is silently dropped from the preview.
    """
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    stage = stage_frame(page)
    expect(stage.locator("button")).to_be_attached()

    # Maximize the attrs editor, add an attribute, close.
    page.click(".cg-control--attrs [data-cg-editor-maximize]")
    page.locator("[data-cg-editor-modal-slot] [data-cg-attrs-input]").fill('data-zz="marker"')
    page.click("button[data-cg-editor-modal-close]")

    # Preview reflects the edit made inside the modal.
    expect(stage.locator("button")).to_have_attribute("data-zz", "marker")


def test_modal_focus_trap_keeps_tab_inside(page: Page, live_gallery: str) -> None:
    """Tab from the last focusable in the modal wraps to the first."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-attrs-input]")
    page.click(".cg-control--attrs [data-cg-editor-maximize]")

    # Focus the close button (last focusable) and tab forward.
    page.locator("button[data-cg-editor-modal-close]").focus()
    page.keyboard.press("Tab")

    # Active element should still be inside the modal.
    in_modal = page.evaluate(
        '() => document.querySelector("[data-cg-editor-modal]").contains(document.activeElement)'
    )
    assert in_modal, "Tab leaked focus outside the modal"
