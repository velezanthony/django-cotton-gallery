"""Theme toggle E2E tests."""

from playwright.sync_api import Page, expect


def test_theme_toggle_switches_to_dark(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    # Default is light: data-theme should not be set.
    html = page.locator("html")
    assert html.get_attribute("data-theme") in (None, "")

    page.click("[data-cg-theme-toggle]")
    expect(html).to_have_attribute("data-theme", "dark")


def test_theme_persists_across_reload(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    page.click("[data-cg-theme-toggle]")
    page.reload()
    # Pre-paint script reads localStorage and sets data-theme before first paint.
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")


def test_theme_toggle_returns_to_light(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    page.click("[data-cg-theme-toggle]")  # → dark
    page.click("[data-cg-theme-toggle]")  # → light
    html = page.locator("html")
    assert html.get_attribute("data-theme") in (None, "")
