"""The grid has to follow the controls.

Props that are not an axis are fixed for the whole grid, so they come from the
form — and the form is serialized a third time in `buildMatrix`, with the same
bug the compare view had.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

# Two enum props become the axes; `framed` is left over as a base param.
PANEL = """{# @description Matrix base-params fixture. #}
{# @prop tone:select['calm', 'loud'] | default:"calm" #}
{# @prop size:select['sm', 'lg'] | default:"sm" #}
{# @prop framed:boolean | default:True #}
<c-vars tone="calm" size="sm" framed=True />
<div data-probe="{{ tone }}-{{ size }}">{% if framed %}<b data-probe-framed>framed</b>{% endif %}</div>
"""

URL = "/django-cotton-gallery/panels/box/"
CELL = "[data-cg-matrix-cell]"
FRAMED_TOGGLE = "[data-cg-controls] label.cg-toggle:has(input[name='framed'])"


@pytest.fixture
def panel_tree(cotton_tree: Path) -> Path:
    """Request BEFORE `live_gallery`: both build on `cotton_tree`."""
    panels = cotton_tree / "cotton" / "panels"
    panels.mkdir(parents=True, exist_ok=True)
    (panels / "box.html").write_text(PANEL)
    reset_caches()
    return cotton_tree


def open_matrix(page: Page) -> None:
    page.click("[data-cg-view='matrix']")
    expect(page.locator(CELL).first).to_be_attached(timeout=5000)
    page.wait_for_timeout(1200)


def framed_cells(page: Page) -> int:
    return sum(
        page.frame_locator(f"{CELL} >> nth={i} >> iframe").locator("[data-probe-framed]").count()
        for i in range(page.locator(CELL).count())
    )


def test_a_default_true_bool_switched_off_is_off_in_every_cell(
    page: Page, panel_tree, live_gallery
):
    page.goto(f"{live_gallery}{URL}")
    page.locator(FRAMED_TOGGLE).click()
    open_matrix(page)

    assert framed_cells(page) == 0, "the grid kept the prop the toggle turned off"


def test_changing_a_non_axis_prop_rebuilds_the_grid(page: Page, panel_tree, live_gallery):
    page.goto(f"{live_gallery}{URL}")
    open_matrix(page)
    expect(page.locator(f"{CELL} iframe")).to_have_count(page.locator(CELL).count(), timeout=10000)
    assert framed_cells(page) == page.locator(CELL).count()

    page.locator(FRAMED_TOGGLE).click()

    # The grid rebuilds and refetches — wait for the probe to go, don't sleep.
    expect(page.locator(f"{CELL} iframe")).to_have_count(page.locator(CELL).count(), timeout=10000)
    expect(
        page.locator(CELL).first.frame_locator("iframe").locator("[data-probe-framed]")
    ).to_have_count(0, timeout=10000)
    assert framed_cells(page) == 0, "the grid ignored the form"


def test_the_hidden_single_preview_is_not_fetched(page: Page, panel_tree, live_gallery):
    """In matrix view the single stage is hidden — rendering into it is wasted."""
    page.goto(f"{live_gallery}{URL}")
    open_matrix(page)

    seen: list[str] = []
    page.on("request", lambda r: seen.append(r.url) if "/preview/" in r.url else None)
    page.locator(FRAMED_TOGGLE).click()
    page.wait_for_timeout(1500)

    cells = page.locator(CELL).count()
    assert len(seen) == cells, f"{len(seen)} requests for {cells} cells"
