"""Preview isolation E2E tests.

The preview used to render into the gallery's own document, which let the
gallery leak into the component in two measurable ways:

  * base.css resets headings with an UNLAYERED rule
    (`:where(.cg-app) :where(h1..h6) { font-size: inherit }`). Unlayered rules
    beat anything inside an `@layer` no matter the specificity, so a consumer
    on Tailwind — whose utilities live in `@layer utilities` — lost every
    heading size inside the preview.
  * `.cg-preview__stage` centers with flex, so a block-level component root
    became a `flex: 0 1 auto` item and shrank to its content instead of
    filling the stage. Children with `flex: 1` then had no free space left
    and collapsed to 0px.

These tests pin the component's own layout and typography. They drive the
component through the frame the stage mounts, so they also fail loudly if the
isolation is removed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from django_cotton_gallery.factories import reset_caches

from ._frames import stage_frame

BANNER_URL = "/django-cotton-gallery/layouts/banner/"

# Consumer typography, declared the way a real stack declares it: inside a
# cascade layer. An inline style would win on its own and prove nothing.
EXTRA_HEAD = """<style>
@layer utilities { .cg-probe-title { font-size: 30px; font-weight: 700; } }
</style>
"""

# Block-level root with a `flex: 1` spacer — the two shapes the old stage broke.
BANNER = """{# @description Full-width banner. Fixture for preview isolation. #}
{# @prop title:text | default:"Isolated" | description:"Heading text" #}
<c-vars title="Isolated" />
<section data-probe-root>
  <h1 class="cg-probe-title">{{ title }}</h1>
  <div style="display:flex;align-items:center;gap:8px">
    <span>A</span>
    <div data-probe-bar style="flex:1;height:1px;background:#000"></div>
    <span>B</span>
  </div>
</section>
"""


@pytest.fixture
def isolation_tree(cotton_tree: Path) -> Path:
    """Add the banner component and a layered consumer stylesheet to the tree.

    Must be requested BEFORE `live_gallery` in the test signature: both depend
    on `cotton_tree`, and pytest builds same-level fixtures in argument order,
    so this is what guarantees the files exist before the catalog is scanned.
    """
    layouts = cotton_tree / "cotton" / "layouts"
    layouts.mkdir(parents=True, exist_ok=True)
    (layouts / "banner.html").write_text(BANNER)

    # `_extra_head.html` is the documented hook for inline consumer assets, and
    # it resolves from TEMPLATES["DIRS"] — which live_gallery points at this tree.
    head = cotton_tree / "django_cotton_gallery"
    head.mkdir(parents=True, exist_ok=True)
    (head / "_extra_head.html").write_text(EXTRA_HEAD)

    reset_caches()
    return cotton_tree


def test_component_heading_keeps_its_own_font_size(page: Page, isolation_tree, live_gallery):
    """The gallery's heading reset must not reach the component."""
    page.goto(f"{live_gallery}{BANNER_URL}")
    heading = stage_frame(page).locator("h1.cg-probe-title")
    expect(heading).to_be_attached(timeout=5000)

    size = heading.evaluate("el => getComputedStyle(el).fontSize")
    assert size == "30px", f"consumer typography was overridden — got {size}"


def test_block_component_fills_the_stage(page: Page, isolation_tree, live_gallery):
    """A block-level root spans the stage instead of shrinking to its content."""
    page.goto(f"{live_gallery}{BANNER_URL}")
    root = stage_frame(page).locator("[data-probe-root]")
    expect(root).to_be_attached(timeout=5000)

    root_width = root.evaluate("el => el.getBoundingClientRect().width")
    body_width = root.evaluate("el => el.ownerDocument.body.clientWidth")
    assert root_width == pytest.approx(body_width, abs=1), (
        f"root shrank to {root_width}px inside a {body_width}px stage"
    )


def test_flex_child_does_not_collapse(page: Page, isolation_tree, live_gallery):
    """`flex: 1` inside the component has free space to claim."""
    page.goto(f"{live_gallery}{BANNER_URL}")
    bar = stage_frame(page).locator("[data-probe-bar]")
    expect(bar).to_be_attached(timeout=5000)

    width = bar.evaluate("el => el.getBoundingClientRect().width")
    assert width > 0, "flex:1 spacer collapsed — the root is not filling the stage"


def test_component_media_queries_use_the_stage_width(page: Page, isolation_tree, live_gallery):
    """The component sees the stage as its viewport, not the browser window.

    This is what makes the viewport switcher more than decoration: at a 1600px
    window the stage is far narrower, so the component's own `innerWidth` has
    to report the stage, not the window.
    """
    page.goto(f"{live_gallery}{BANNER_URL}")
    root = stage_frame(page).locator("[data-probe-root]")
    expect(root).to_be_attached(timeout=5000)

    inner = root.evaluate("el => el.ownerDocument.defaultView.innerWidth")
    outer = page.evaluate("() => window.innerWidth")
    assert inner < outer, f"component viewport ({inner}px) tracks the window ({outer}px)"
