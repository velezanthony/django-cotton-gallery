"""Pins + Recents E2E tests.

The personal sections (pinned + recently-viewed) are injected into the
sidebar client-side by power-tools.js and persisted in localStorage. They
live in the DOM but are `display:none` by default — the toolbar star/clock
filters (`cg-sidebar--show-pins-only` / `--show-recents-only`) reveal them.
Each Playwright test gets a fresh context, so there is no cross-test bleed.
"""

from playwright.sync_api import Page, expect


def test_visiting_components_populates_recents(page: Page, live_gallery):
    """Viewing a component records it in Recents; the clock filter reveals it."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/input/")
    # Move on to button so "input" is an unambiguous *previously*-viewed entry.
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.locator("[data-cg-filter='recents']").click()
    recents = page.locator("[data-cg-personal='recents']")
    expect(recents).to_be_visible()
    expect(recents.locator("[data-cg-component='input']")).to_have_count(1)


def test_pinning_adds_component_to_pins_section(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    pin = page.locator("[data-cg-pin-toggle]")
    expect(pin).to_have_attribute("data-cg-pinned", "false")
    pin.click()
    expect(pin).to_have_attribute("data-cg-pinned", "true")
    # Reveal the pins section via its toolbar filter, then assert the entry.
    page.locator("[data-cg-filter='pins']").click()
    pins = page.locator("[data-cg-personal='pins']")
    expect(pins).to_be_visible()
    expect(pins.locator("[data-cg-component='button']")).to_have_count(1)


def test_pin_persists_across_reload(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.locator("[data-cg-pin-toggle]").click()
    page.reload()
    # State is rehydrated from localStorage: star still pressed, entry present.
    expect(page.locator("[data-cg-pin-toggle]")).to_have_attribute("data-cg-pinned", "true")
    expect(
        page.locator("[data-cg-personal='pins'] [data-cg-component='button']")
    ).to_have_count(1)


def test_unpinning_removes_the_entry(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    pin = page.locator("[data-cg-pin-toggle]")
    pin.click()  # pin
    expect(
        page.locator("[data-cg-personal='pins'] [data-cg-component='button']")
    ).to_have_count(1)
    pin.click()  # unpin
    expect(pin).to_have_attribute("data-cg-pinned", "false")
    # The injected link is gone from the DOM entirely (section emptied).
    expect(
        page.locator("[data-cg-personal='pins'] [data-cg-component='button']")
    ).to_have_count(0)


def test_pinned_link_is_excluded_from_search(page: Page, live_gallery):
    """Regression guard: a pinned component injects a second sidebar link,
    but search must still surface it exactly once (see sidebar.js dedupe)."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.locator("[data-cg-pin-toggle]").click()
    expect(
        page.locator("[data-cg-personal='pins'] [data-cg-component='button']")
    ).to_have_count(1)
    page.locator("[data-cg-search]").fill("but")
    expect(page.locator(".cg-sidebar__suggestion")).to_have_count(1)
