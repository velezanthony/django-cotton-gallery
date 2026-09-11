"""A search suggestion has to be readable.

The path sized itself first, so `crea-comunidad-modal` showed as `crea-co…`
beside a full `molecules / overlay`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

NAME = ".cg-sidebar__suggestion-name"
PATH = ".cg-sidebar__suggestion-path"
SEARCH = ".cg-sidebar__search-input"

COMPONENT = "{# @description A search suggestion fixture. #}\n<div>x</div>\n"


@pytest.fixture
def long_name_tree(cotton_tree: Path) -> Path:
    """Request BEFORE `live_gallery`: both build on `cotton_tree`."""
    deep = cotton_tree / "cotton" / "molecules" / "overlay"
    deep.mkdir(parents=True, exist_ok=True)
    # Too long to share the line with `molecules / overlay`…
    (deep / "confirmation-dialog-panel.html").write_text(COMPONENT)
    # …and one that fits beside it.
    (deep / "tip.html").write_text(COMPONENT)
    reset_caches()
    return cotton_tree


def open_suggestions(page: Page, query: str) -> None:
    """The dropdown renders more than once — measuring early reads stale boxes."""
    page.locator(SEARCH).fill(query)
    expect(page.locator("[role=option]")).to_have_count(1, timeout=5000)
    expect(page.locator(NAME).first).to_be_visible()


def test_the_component_name_is_not_truncated(page: Page, long_name_tree, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    open_suggestions(page, "confirmation")

    truncated = page.locator(NAME).first.evaluate(
        "el => el.scrollWidth > Math.ceil(el.getBoundingClientRect().width) + 1"
    )
    text = page.locator(NAME).first.inner_text()
    assert not truncated, f"the name is clipped: {text!r}"


def test_they_share_a_line_when_they_fit(page: Page, long_name_tree, live_gallery):
    """Name left, path right — wrapping is for when there is no room."""
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    open_suggestions(page, "tip")

    head = page.locator(".cg-sidebar__suggestion-head").first.bounding_box()
    path = page.locator(PATH).first.bounding_box()
    name = page.locator(NAME).first.bounding_box()

    assert abs(path["y"] - name["y"]) < 6, (
        f"they wrapped with room to spare — path {path}, name {name}"
    )
    assert abs(name["x"] - head["x"]) < 2, "the name is not against the left edge"
    assert abs((path["x"] + path["width"]) - (head["x"] + head["width"])) < 2, (
        "the path is not against the right edge"
    )


def test_the_path_moves_above_when_it_does_not_fit(page: Page, long_name_tree, live_gallery):
    """Where it lives first, then what you searched for."""
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    open_suggestions(page, "confirmation")

    path = page.locator(PATH).first.bounding_box()
    name = page.locator(NAME).first.bounding_box()
    assert path["y"] + path["height"] <= name["y"] + 2, (
        f"the path is not above the name — path {path}, name {name}"
    )
