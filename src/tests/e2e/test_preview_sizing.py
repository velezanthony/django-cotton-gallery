"""How tall the preview frame gets.

The frame is sized from `documentElement.scrollHeight`, and a `position: fixed`
element contributes nothing to it. A component that anchors to the viewport —
a modal, a drawer, a toast layer — therefore sizes itself to a frame that was
measured as if it did not exist, and gets clipped.

Fullscreen is where it shows worst: the slot has room for a real viewport and
the component still renders in a sliver.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

from ._frames import stage_frame

OVERLAY_URL = "/django-cotton-gallery/overlays/sheet/"

# Nothing in flow but a 20px button; everything visible is anchored to the
# viewport. Flow height is ~20px, which is what the frame used to measure.
OVERLAY = """{# @description Fixed overlay. Fixture for frame sizing. #}
<div>
  <button style="height:20px">open</button>
  <div data-probe-overlay style="position:fixed;inset:0;background:rgba(0,0,0,.4)"></div>
</div>
"""


@pytest.fixture
def overlay_tree(cotton_tree: Path) -> Path:
    """Request BEFORE `live_gallery`: both build on `cotton_tree`."""
    overlays = cotton_tree / "cotton" / "overlays"
    overlays.mkdir(parents=True, exist_ok=True)
    (overlays / "sheet.html").write_text(OVERLAY)
    reset_caches()
    return cotton_tree


def test_fullscreen_gives_the_component_a_real_viewport(page: Page, overlay_tree, live_gallery):
    """In fullscreen the frame fills the slot instead of measuring the flow."""
    page.goto(f"{live_gallery}{OVERLAY_URL}")
    overlay = stage_frame(page).locator("[data-probe-overlay]")
    expect(overlay).to_be_attached(timeout=5000)

    page.click("[data-cg-preview-fullscreen]")
    expect(page.locator("[data-cg-fs-preview-slot] iframe")).to_be_attached()

    height = overlay.evaluate("el => el.getBoundingClientRect().height")
    slot = page.locator("[data-cg-fs-preview-slot]").evaluate(
        "el => el.getBoundingClientRect().height"
    )
    assert height > 400, f"overlay rendered in a {height}px sliver"
    assert height == pytest.approx(slot, rel=0.15), (
        f"overlay is {height}px inside a {slot}px fullscreen slot"
    )
