"""Sidebar state E2E tests.

Toolbar toggles that only mutate presentation + persist in localStorage:
lint-badge visibility, per-category collapse, and the mutually-exclusive
pins/recents personal filters.
"""

import re

from playwright.sync_api import Page, expect


def test_lint_badge_toggle_hides_and_persists(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    sidebar = page.locator("[data-cg-sidebar]")
    toggle = page.locator("[data-cg-toggle-issues]")
    expect(toggle).to_have_attribute("data-cg-hidden", "false")
    toggle.click()
    expect(toggle).to_have_attribute("data-cg-hidden", "true")
    expect(sidebar).to_have_class(re.compile(r"cg-sidebar--hide-lint"))
    # Survives a reload.
    page.reload()
    expect(page.locator("[data-cg-toggle-issues]")).to_have_attribute("data-cg-hidden", "true")


def test_collapsing_category_hides_its_links_and_persists(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    toggle = page.locator("[data-cg-toggle='atoms']")
    target = page.locator("[data-cg-collapse='atoms']")
    expect(target).to_be_visible()
    toggle.click()
    expect(target).to_be_hidden()
    # Persisted collapse state is re-applied on reload.
    page.reload()
    expect(page.locator("[data-cg-collapse='atoms']")).to_be_hidden()


def test_personal_filters_are_mutually_exclusive(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    sidebar = page.locator("[data-cg-sidebar]")
    pins = page.locator("[data-cg-filter='pins']")
    recents = page.locator("[data-cg-filter='recents']")

    pins.click()
    expect(pins).to_have_attribute("data-cg-on", "true")
    expect(sidebar).to_have_class(re.compile(r"cg-sidebar--show-pins-only"))

    # Selecting recents deactivates pins — only one filter at a time.
    recents.click()
    expect(recents).to_have_attribute("data-cg-on", "true")
    expect(pins).to_have_attribute("data-cg-on", "false")
    expect(sidebar).to_have_class(re.compile(r"cg-sidebar--show-recents-only"))
    expect(sidebar).not_to_have_class(re.compile(r"cg-sidebar--show-pins-only"))


def test_personal_filter_toggles_off_on_second_click(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    sidebar = page.locator("[data-cg-sidebar]")
    pins = page.locator("[data-cg-filter='pins']")
    pins.click()
    expect(pins).to_have_attribute("data-cg-on", "true")
    pins.click()  # click again → back to the full catalog
    expect(pins).to_have_attribute("data-cg-on", "false")
    expect(sidebar).not_to_have_class(re.compile(r"cg-sidebar--show-pins-only"))
