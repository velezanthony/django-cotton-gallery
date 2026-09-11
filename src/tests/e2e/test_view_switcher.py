"""View switcher E2E tests — what the toolbar offers per view."""

from __future__ import annotations

from playwright.sync_api import Page, expect

BUTTON_URL = "/django-cotton-gallery/atoms/button/"

VIEWPORTS = ".cg-vp-btn[data-cg-viewport]"
FULLSCREEN = "[data-cg-preview-fullscreen]"


def test_matrix_view_disables_the_viewport_buttons(page: Page, live_gallery):
    """The matrix replaces the single stage, so there is nothing to resize."""
    page.goto(f"{live_gallery}{BUTTON_URL}")
    page.click("[data-cg-view='matrix']")

    for i in range(page.locator(VIEWPORTS).count()):
        expect(page.locator(VIEWPORTS).nth(i)).to_be_disabled()


def test_matrix_view_keeps_fullscreen_available(page: Page, live_gallery):
    """Fullscreen opens whatever the preview shows, matrix included."""
    page.goto(f"{live_gallery}{BUTTON_URL}")
    page.click("[data-cg-view='matrix']")

    expect(page.locator(FULLSCREEN)).to_be_enabled()


def test_leaving_matrix_restores_the_viewport_buttons(page: Page, live_gallery):
    page.goto(f"{live_gallery}{BUTTON_URL}")
    page.click("[data-cg-view='matrix']")
    page.click("[data-cg-view='preview']")

    for i in range(page.locator(VIEWPORTS).count()):
        expect(page.locator(VIEWPORTS).nth(i)).to_be_enabled()
