"""Matrix cells get the same isolated stage as every other surface.

A grid of every prop combination is the densest place the gallery renders
components, and the last one still writing them into its own page.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

URL = "/django-cotton-gallery/grids/tile/"
MATRIX = "[data-cg-preview-matrix]"
CELL = "[data-cg-matrix-cell]"
CELL_FRAME = "[data-cg-matrix-cell] iframe"

# Two enum props so the grid has both axes, and an overlay anchored to the
# viewport — one per cell is the worst case for leaking onto the page.
TILE = """{# @description Grid fixture. #}
{# @prop tone:select['calm', 'loud'] | default:"calm" #}
{# @prop size:select['sm', 'lg'] | default:"sm" #}
<c-vars tone="calm" size="sm" />
<div data-probe-tile>{{ tone }}/{{ size }}</div>
<div data-probe-overlay style="position:fixed;inset:0;background:rgba(0,0,0,.25)"></div>
"""


@pytest.fixture
def grid_tree(cotton_tree: Path) -> Path:
    """Request BEFORE `live_gallery`: both build on `cotton_tree`."""
    grids = cotton_tree / "cotton" / "grids"
    grids.mkdir(parents=True, exist_ok=True)
    (grids / "tile.html").write_text(TILE)
    reset_caches()
    return cotton_tree


def open_matrix(page: Page, live_gallery: str) -> None:
    page.goto(f"{live_gallery}{URL}")
    page.click("[data-cg-view='matrix']")
    expect(page.locator(CELL).first).to_be_attached(timeout=5000)


def test_every_cell_renders_in_its_own_document(page: Page, grid_tree, live_gallery):
    open_matrix(page, live_gallery)
    expect(page.locator(CELL_FRAME).first).to_be_attached(timeout=5000)

    page.wait_for_timeout(1200)
    cells = page.locator(CELL).count()
    frames = page.locator(CELL_FRAME).count()
    assert frames == cells, f"{frames} frames for {cells} cells"


def test_a_cell_does_not_leak_onto_the_page(page: Page, grid_tree, live_gallery):
    open_matrix(page, live_gallery)
    expect(page.locator(CELL_FRAME).first).to_be_attached(timeout=5000)
    page.wait_for_timeout(1200)

    covering = page.evaluate("""() => [...document.querySelectorAll('body *')].some(el => {
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return cs.position === 'fixed'
            && r.width > innerWidth * 0.8 && r.height > innerHeight * 0.8
            && cs.display !== 'none';
    })""")
    assert not covering, "a cell's overlay escaped onto the page"
