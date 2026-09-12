"""The stage can be dragged taller from its bottom edge.

A component anchored to the viewport (a modal, a drawer) is designed for a
screen, not for the height of its own flow content — and the gallery has no
business guessing how tall that screen should be. It hands the user a grip
instead.

The drag wins while you are on the page: auto-sizing stops fighting it. It is
not persisted; navigating to another component rebuilds the stage.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

BUTTON_URL = "/django-cotton-gallery/atoms/button/"
STAGE = "[data-cg-preview-stage]"
FRAME = "[data-cg-preview-stage] iframe"
GRIP = "[data-cg-stage-grip]"


def test_the_grip_spans_the_whole_bottom_edge(page: Page, live_gallery):
    """A corner handle is a pixel hunt — the whole edge is the target."""
    page.goto(f"{live_gallery}{BUTTON_URL}")
    expect(page.locator(GRIP)).to_be_visible(timeout=5000)

    grip = page.locator(GRIP).bounding_box()
    stage = page.locator(STAGE).bounding_box()
    assert grip["width"] == stage["width"], (
        f"grip is {grip['width']}px across a {stage['width']}px stage"
    )
    assert grip["y"] >= stage["y"] + stage["height"] - 2, "grip is not at the bottom edge"


def test_the_grip_explains_itself(page: Page, live_gallery):
    page.goto(f"{live_gallery}{BUTTON_URL}")
    grip = page.locator(GRIP)
    expect(grip).to_be_visible(timeout=5000)

    assert (grip.get_attribute("title") or "").strip(), "no hover hint on the grip"
    assert (grip.get_attribute("aria-label") or "").strip(), "no accessible name"


def test_dragging_the_grip_grows_the_stage(page: Page, live_gallery):
    page.goto(f"{live_gallery}{BUTTON_URL}")
    expect(page.locator(FRAME)).to_be_attached(timeout=5000)

    before = page.locator(STAGE).bounding_box()["height"]
    box = page.locator(GRIP).bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 300, steps=10)
    page.mouse.up()
    page.wait_for_timeout(400)

    after = page.locator(STAGE).bounding_box()["height"]
    assert after > before + 250, f"stage went from {before}px to {after}px"

    frame = page.locator(FRAME).bounding_box()["height"]
    assert frame > before + 200, f"the frame did not follow the drag — {frame}px"


def test_a_dragged_height_survives_a_re_render(page: Page, live_gallery):
    """Auto-sizing must not undo the drag on the next render."""
    page.goto(f"{live_gallery}{BUTTON_URL}")
    expect(page.locator(FRAME)).to_be_attached(timeout=5000)

    page.locator(STAGE).evaluate("el => { el.style.height = '600px'; }")
    page.locator("[data-cg-slot-input], [data-cg-attrs-input]").first.fill("dragged")
    page.wait_for_timeout(800)

    height = page.locator(STAGE).evaluate("el => el.getBoundingClientRect().height")
    assert height == 600, f"the drag was undone — stage is {height}px"
