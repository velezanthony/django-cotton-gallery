"""E2E tests for the slot intellisense popover's scroll + viewport behaviour.

Both cover `createPopover` (js/popover.js), shared by the slot intellisense,
the attrs autocomplete, and the enum dropdowns.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

MENU = "[data-cg-slot-editor] [data-cg-intellisense]"


def _open_tag_suggestions(page: Page, live_gallery: str, width: int = 1600) -> None:
    """Land on a component with a slot and open the tag suggestion list."""
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.wait_for_selector("[data-cg-slot-textarea]")

    page.locator("[data-cg-slot-textarea]").first.click()
    # A bare `<` offers every HTML tag plus every Cotton component — far more
    # than the menu's max-height fits, so the list is scrollable.
    page.keyboard.type("<")
    expect(page.locator(MENU)).to_be_visible()


def test_intellisense_survives_arrowing_past_the_visible_items(
    page: Page, live_gallery: str
) -> None:
    """ArrowDown scrolls the list into view — that must not close the menu.

    `scrollIntoView` on the highlighted item scrolls the menu itself; the
    popover's window-level scroll listener used to catch that in the capture
    phase and close the popover on the first item below the fold.
    """
    _open_tag_suggestions(page, live_gallery)
    menu = page.locator(MENU)

    # Well past the ~5 items that fit in the menu's 14rem max-height.
    for _ in range(12):
        page.keyboard.press("ArrowDown")

    expect(menu).to_be_visible()
    assert menu.evaluate("el => el.scrollTop") > 0, (
        "the highlighted item never scrolled into view — the list is not tall "
        "enough to exercise the regression"
    )


def test_intellisense_scrolling_the_list_keeps_it_open(page: Page, live_gallery: str) -> None:
    """Wheel-scrolling inside the list must not dismiss it either."""
    _open_tag_suggestions(page, live_gallery)
    menu = page.locator(MENU)

    menu.hover()
    page.mouse.wheel(0, 120)
    # Settle on the wheel's outcome before asserting — either the list scrolled
    # or the popover closed. Reading straight after the wheel would race the
    # scroll event and pass on a stale "still visible".
    page.wait_for_function(
        "el => el.scrollTop > 0 || el.hasAttribute('hidden')", arg=menu.element_handle()
    )

    expect(menu).to_be_visible()


def test_intellisense_stays_inside_the_viewport(page: Page, live_gallery: str) -> None:
    """The caret sits in the right-hand controls panel — the menu is anchored
    to it and must be clamped so it never runs off the right edge."""
    # A narrow window leaves the menu no room to the right of the caret.
    _open_tag_suggestions(page, live_gallery, width=1280)

    box = page.locator(MENU).bounding_box()
    assert box is not None
    viewport_width = page.evaluate("() => window.innerWidth")

    right = box["x"] + box["width"]
    assert right <= viewport_width, (
        f"menu right edge {right} overflows the {viewport_width}px viewport "
        f"by {right - viewport_width}px"
    )
    assert box["x"] >= 0, f"menu left edge {box['x']} is off-screen"
