"""Sidebar search E2E tests."""

from playwright.sync_api import Page, expect


def test_search_filters_components(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    # Suggestions panel should show with the button match.
    suggestions = page.locator("[data-cg-suggestions]")
    expect(suggestions).to_be_visible()
    expect(suggestions.locator(".cg-sidebar__suggestion")).to_have_count(1)
    expect(suggestions).to_contain_text("button")


def test_search_clear_button_resets(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    page.click("[data-cg-search-clear]")
    expect(search).to_have_value("")


def test_slash_focuses_search(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    page.keyboard.press("/")
    search = page.locator("[data-cg-search]")
    expect(search).to_be_focused()


def test_escape_clears_query(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    search.press("Escape")
    expect(search).to_have_value("")
