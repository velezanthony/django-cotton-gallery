"""Live preview update E2E tests."""

import re

from playwright.sync_api import Page, expect

from ._frames import stage_frame


def test_changing_variant_updates_preview(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    stage = stage_frame(page)
    expect(stage.locator("button")).to_be_attached()
    expect(stage.locator("button")).to_have_class(re.compile(r"btn-primary"))

    # Open the variant dropdown and pick "danger". The popover is `position:
    # fixed` and may land partly off-screen on a 1280x800 headless viewport,
    # so use `force=True` to skip actionability checks.
    page.click("[data-cg-dropdown-trigger]:has-text('primary')")
    page.locator("[data-cg-dropdown-option='danger']").click(force=True)

    expect(stage.locator("button")).to_have_class(re.compile(r"btn-danger"))


def test_url_updates_when_variant_changes(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.click("[data-cg-dropdown-trigger]:has-text('primary')")
    page.locator("[data-cg-dropdown-option='danger']").click(force=True)
    expect(page).to_have_url(re.compile(r"variant=danger"))


def test_preview_renders_on_load(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    stage = stage_frame(page)
    # Initial preview must render without user interaction. Element is sizeless
    # without slot content, so check DOM presence rather than visibility.
    expect(stage.locator("button")).to_be_attached(timeout=5000)
