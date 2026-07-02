"""Copy-to-clipboard + share-link E2E tests.

Clipboard permissions are granted in the e2e `browser_context_args` fixture,
so the clipboard can be read back to assert what each button copied.
"""

import re

from playwright.sync_api import Page, expect


def _clipboard(page: Page) -> str:
    return page.evaluate("() => navigator.clipboard.readText()")


def test_copy_permalink_copies_current_url(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.locator("[data-cg-copy-permalink]").click()
    assert _clipboard(page) == page.url


def test_copy_tag_copies_cotton_snippet(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.locator("[data-cg-copy-target='#cg-detail-tag']").click()
    clip = _clipboard(page)
    assert "c-atoms.button" in clip


def test_copy_button_shows_copied_feedback(page: Page, live_gallery):
    """The copy button flashes a `cg-copied` class on success (~1.5s)."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    btn = page.locator("[data-cg-copy-target='#cg-detail-tag']")
    btn.click()
    expect(btn).to_have_class(re.compile(r"cg-copied"))
