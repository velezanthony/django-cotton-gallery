"""One interaction, one preview request.

Checkboxes, radios and selects fire `input` AND `change`, and the custom
dropdown dispatches both by hand — so an instant control that is wired to both
listeners fetches twice and aborts its own first attempt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

KNOBS = """{# @description Instant-controls fixture. #}
{# @prop shown:boolean | default:True #}
{# @prop tone:select['calm', 'loud'] | default:"calm" #}
<c-vars shown=True tone="calm" />
<div data-probe>{{ tone }}{% if shown %}+{% endif %}</div>
"""

FRAME = "[data-cg-preview-stage] iframe"


@pytest.fixture
def knobs_tree(cotton_tree: Path) -> Path:
    """Request BEFORE `live_gallery`: both build on `cotton_tree`."""
    atoms = cotton_tree / "cotton" / "atoms"
    atoms.mkdir(parents=True, exist_ok=True)
    (atoms / "knobs.html").write_text(KNOBS)
    reset_caches()
    return cotton_tree


def count_previews(page: Page) -> list[str]:
    seen: list[str] = []
    page.on("request", lambda r: seen.append(r.url) if "/preview/" in r.url else None)
    return seen


def test_a_toggle_fires_one_request(page: Page, knobs_tree, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/knobs/")
    expect(page.locator(FRAME)).to_be_attached(timeout=5000)

    seen = count_previews(page)
    page.locator("[data-cg-controls] label.cg-toggle:has(input[name='shown'])").click()
    page.wait_for_timeout(800)

    assert len(seen) == 1, f"{len(seen)} requests for one click: {seen}"
