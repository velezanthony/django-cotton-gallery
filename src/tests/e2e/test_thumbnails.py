"""Index thumbnails render in their own document, and get recycled.

Same three problems the detail preview had — the gallery's heading reset
winning over the consumer's `@layer`, a `position: fixed` component escaping
its card, scripts never running — except a card is 160px tall and there are
as many of them as the catalog has components.

Which is the second half: a frame per card, kept forever, means a JS runtime
per card kept forever. They are dropped when they scroll well out of view and
rebuilt on the way back.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

from ._frames import STAGE_FRAME  # noqa: F401  (kept alongside the detail helper)

INDEX = "/django-cotton-gallery/"
THUMB = "[data-cg-thumb]"
THUMB_FRAME = "[data-cg-thumb] iframe"

# Anchored to the viewport, like a modal backdrop: escapes its card unless the
# card is a document of its own.
OVERLAY = """{# @description Fixed overlay. Fixture for thumbnail isolation. #}
<div>
  <button style="height:20px">open</button>
  <div data-probe-overlay style="position:fixed;inset:0;background:rgba(0,0,0,.4)"></div>
</div>
"""


# Enough rows that the first cards end up well past the recycler's margin.
FILLER_COUNT = 60


@pytest.fixture
def overlay_tree(cotton_tree: Path) -> Path:
    """Request BEFORE `live_gallery`: both build on `cotton_tree`."""
    overlays = cotton_tree / "cotton" / "overlays"
    overlays.mkdir(parents=True, exist_ok=True)
    (overlays / "sheet.html").write_text(OVERLAY)

    filler = cotton_tree / "cotton" / "filler"
    filler.mkdir(parents=True, exist_ok=True)
    for i in range(FILLER_COUNT):
        (filler / f"card-{i:02d}.html").write_text(
            f"{{# @description Filler {i}. #}}\n<div data-probe-filler>{i}</div>\n"
        )

    reset_caches()
    return cotton_tree


def test_a_thumbnail_renders_in_its_own_document(page: Page, overlay_tree, live_gallery):
    page.goto(f"{live_gallery}{INDEX}")
    expect(page.locator(THUMB_FRAME).first).to_be_attached(timeout=5000)


def test_a_fixed_component_stays_inside_its_card(page: Page, overlay_tree, live_gallery):
    """The overlay covers its own 160px card, not the index."""
    page.goto(f"{live_gallery}{INDEX}")
    expect(page.locator(THUMB_FRAME).first).to_be_attached(timeout=5000)
    page.wait_for_timeout(1200)

    covering = page.evaluate("""() => [...document.querySelectorAll('body *')].some(el => {
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return cs.position === 'fixed'
            && r.width > innerWidth * 0.8 && r.height > innerHeight * 0.8
            && cs.display !== 'none';
    })""")
    assert not covering, "a thumbnail's overlay escaped onto the index"


def test_frames_are_dropped_when_scrolled_away(page: Page, overlay_tree, live_gallery):
    """A JS runtime per card, kept forever, is the cost we are avoiding."""
    page.goto(f"{live_gallery}{INDEX}")
    expect(page.locator(THUMB_FRAME).first).to_be_attached(timeout=5000)

    total = page.locator(THUMB).count()
    if total < 8:
        pytest.skip(f"catalog too small to scroll past ({total} cards)")

    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")

    # Recycling is driven by an IntersectionObserver — poll for it.
    expect(page.locator(THUMB_FRAME)).not_to_have_count(total, timeout=10000)


def test_a_recycled_card_comes_back(page: Page, overlay_tree, live_gallery):
    page.goto(f"{live_gallery}{INDEX}")
    expect(page.locator(THUMB_FRAME).first).to_be_attached(timeout=5000)

    if page.locator(THUMB).count() < 8:
        pytest.skip("catalog too small to scroll past")

    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1200)
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(1500)

    expect(page.locator(THUMB_FRAME).first).to_be_attached(timeout=5000)
