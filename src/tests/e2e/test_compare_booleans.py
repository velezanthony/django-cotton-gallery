"""A default-True boolean must be switchable off in compare, as in the detail view.

The two views serialize the controls form separately, and only one of them
sends the explicit `false` the server needs: an absent param falls back to the
prop default (`tag_builder._resolve_attrs`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

FLAG = """{# @description Boolean fixture. #}
{# @prop shown:boolean | default:True #}
<c-vars shown=True />
<div>{% if shown %}<span data-probe-on>on</span>{% else %}<span data-probe-off>off</span>{% endif %}</div>
"""

PANEL = "[data-cg-compare-side='a']"
FRAME = f"{PANEL} [data-cg-preview-stage] iframe"


@pytest.fixture
def flag_tree(cotton_tree: Path) -> Path:
    """Request BEFORE `live_gallery`: both build on `cotton_tree`."""
    atoms = cotton_tree / "cotton" / "atoms"
    atoms.mkdir(parents=True, exist_ok=True)
    (atoms / "flag.html").write_text(FLAG)
    reset_caches()
    return cotton_tree


def test_unchecking_it_in_compare_turns_it_off(page: Page, flag_tree, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/compare/?a=atoms/flag&b=atoms/flag")
    expect(page.locator(FRAME).first).to_be_attached(timeout=5000)

    body = page.frame_locator(FRAME).locator("body")
    expect(body.locator("[data-probe-on]")).to_be_attached(timeout=5000)

    # The input is visually hidden behind `.cg-toggle__track` — click the label.
    page.locator(f"{PANEL} [data-cg-controls] label:has(input[name='shown'])").click()
    expect(body.locator("[data-probe-off]")).to_be_attached(timeout=5000)
