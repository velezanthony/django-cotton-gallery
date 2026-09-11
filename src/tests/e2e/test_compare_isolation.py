"""The compare view gets the same stage as the detail preview.

Two panels side by side is exactly where the gallery leaking into the
component hurts most: you are there to judge the difference between them.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

COMPARE = "/django-cotton-gallery/compare/?a=atoms/button&b=atoms/input"
PANEL = "[data-cg-compare-side]"
FRAME = "[data-cg-compare-side] [data-cg-preview-stage] iframe"
GRIP = "[data-cg-compare-side] [data-cg-stage-grip]"


def test_both_panels_render_in_their_own_document(page: Page, live_gallery):
    page.goto(f"{live_gallery}{COMPARE}")
    expect(page.locator(PANEL).first).to_be_attached(timeout=5000)

    expect(page.locator(FRAME).first).to_be_attached(timeout=5000)
    assert page.locator(FRAME).count() == page.locator(PANEL).count()


def test_each_panel_has_its_own_grip(page: Page, live_gallery):
    page.goto(f"{live_gallery}{COMPARE}")
    expect(page.locator(FRAME).first).to_be_attached(timeout=5000)

    assert page.locator(GRIP).count() == page.locator(PANEL).count()


def test_dragging_one_panel_leaves_the_other_alone(page: Page, live_gallery):
    """Panels are compared, not linked — one taller must not move the other."""
    page.goto(f"{live_gallery}{COMPARE}")
    expect(page.locator(FRAME).first).to_be_attached(timeout=5000)

    stages = page.locator(f"{PANEL} [data-cg-preview-stage]")
    other_before = stages.nth(1).bounding_box()["height"]

    box = page.locator(GRIP).first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 250, steps=10)
    page.mouse.up()
    page.wait_for_timeout(400)

    dragged = stages.nth(0).bounding_box()["height"]
    other_after = stages.nth(1).bounding_box()["height"]
    assert dragged > other_before + 150, f"the drag did not take ({dragged}px)"
    assert other_after == other_before, f"the other panel moved: {other_before} → {other_after}"
