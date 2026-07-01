"""SPA navigation E2E tests."""

from playwright.sync_api import Page, expect


def test_sidebar_link_navigates_to_detail(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    page.click("[data-cg-component='button']")
    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    expect(page.locator("h1.cg-detail__title")).to_contain_text("button")


def test_back_button_returns_to_index(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    # Wait for the SPA to be ready before navigating.
    page.wait_for_load_state("networkidle")
    page.click("[data-cg-component='button']")
    page.wait_for_url(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.go_back()
    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/")


def test_active_link_highlights_current_component(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    # The sidebar surfaces the active component in multiple places
    # (top personal-row + catalog tree). ALL matching links should pick
    # up `cg-active` to mirror the current detail page — verified by
    # asserting that no matching link lacks the class.
    expect(page.locator("[data-cg-component='button']").first).to_be_attached()
    expect(page.locator("[data-cg-component='button']:not(.cg-active)")).to_have_count(0)
