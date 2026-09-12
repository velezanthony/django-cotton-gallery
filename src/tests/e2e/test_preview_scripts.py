"""Inline `<script>` in a component runs in the preview.

`innerHTML` does not execute scripts it inserts — that is the HTML spec, not a
quirk. A component that ships its own `<script>` (defining the object its
`x-data` calls, registering a web component, wiring a plain listener) therefore
rendered dead in the preview while working everywhere else.

Deliberately framework-free: the gallery is agnostic about what the consumer
brings, so the fixture uses plain DOM and a global. Anything that needs Alpine
or HTMX to prove the point would be testing their bootstrap, not ours.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

from ._frames import stage_frame

WIDGET_URL = "/django-cotton-gallery/widgets/scripted/"

WIDGET = """{# @description Component with its own script. Fixture for script execution. #}
<div>
  <span data-probe-flag>pending</span>
</div>
<script>
  window.probeFactory = function () { return "from the component"; };
  document.querySelector('[data-probe-flag]').textContent = 'ran';
</script>
"""


@pytest.fixture
def widget_tree(cotton_tree: Path) -> Path:
    """Request BEFORE `live_gallery`: both build on `cotton_tree`."""
    widgets = cotton_tree / "cotton" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)
    (widgets / "scripted.html").write_text(WIDGET)
    reset_caches()
    return cotton_tree


def test_inline_script_runs(page: Page, widget_tree, live_gallery):
    page.goto(f"{live_gallery}{WIDGET_URL}")
    flag = stage_frame(page).locator("[data-probe-flag]")

    expect(flag).to_have_text("ran", timeout=5000)


def test_inline_script_defines_globals_for_the_component(page: Page, widget_tree, live_gallery):
    """What `x-data="factory()"` needs: the global exists on the frame's window."""
    page.goto(f"{live_gallery}{WIDGET_URL}")
    flag = stage_frame(page).locator("[data-probe-flag]")
    expect(flag).to_be_attached(timeout=5000)

    result = flag.evaluate("el => el.ownerDocument.defaultView.probeFactory?.()")
    assert result == "from the component", f"the component's global was not defined: {result!r}"
