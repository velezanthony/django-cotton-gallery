"""Replacing a panel has to take its in-flight preview fetch with it.

`sideAbort` cancels the fetch for the panel chrome; the one rendering the
component was left running and mounted a frame into a stage already detached.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

COMPARE = "/django-cotton-gallery/compare/?a=atoms/button&b=atoms/input"
SIDE_A = "[data-cg-compare-side='a']"
FRAME = f"{SIDE_A} [data-cg-preview-stage] iframe"
TOGGLE = f"{SIDE_A} [data-cg-controls] label.cg-toggle:has(input[name='loading'])"

# A localhost render lands in milliseconds — hold the request back so the panel
# is replaced while it is still on the wire. Delaying in the page (not in a
# route handler) keeps Playwright's own thread free.
SLOW_PREVIEW = """
const orig = window.fetch;
window.fetch = (...a) => String(a[0]).includes('/preview/')
  ? new Promise((res, rej) => setTimeout(() => orig(...a).then(res, rej), 1500))
  : orig(...a);
"""


def test_switching_component_drops_the_pending_render(page: Page, live_gallery):
    page.add_init_script(SLOW_PREVIEW)
    page.goto(f"{live_gallery}{COMPARE}")
    expect(page.locator(FRAME)).to_be_attached(timeout=15000)

    page.evaluate(f'window.__oldStage = document.querySelector("{SIDE_A} [data-cg-preview-stage]")')
    page.locator(TOGGLE).click()
    page.locator(".cg-combo__trigger").first.click()
    page.locator("[role=option]", has_text="atoms/input").first.click()

    expect(page.locator(f"{SIDE_A} .cg-compare__panel-title")).to_have_text(
        "atoms/input", timeout=10000
    )
    page.wait_for_timeout(3000)

    detached = page.evaluate(
        "() => ({ inDoc: window.__oldStage.isConnected, frames: window.__oldStage.querySelectorAll('iframe').length })"
    )
    assert detached["inDoc"] is False, "the panel was not replaced — the test proves nothing"
    assert detached["frames"] == 0, "a frame was mounted into the stage that had already gone"
