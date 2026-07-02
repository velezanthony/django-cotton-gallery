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


def test_search_enter_navigates_to_first_match(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    search.press("Enter")
    # Enter activates the first suggestion → navigates to that component.
    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/atoms/button/")


def test_search_enter_dismisses_suggestions_and_clears(page: Page, live_gallery):
    """After Enter navigates, the dropdown must close and the query reset.

    The SPA keeps the sidebar mounted across navigations, so a lingering
    dropdown + stale query would sit on top of the destination page.
    """
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    search.press("Enter")
    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    expect(page.locator("[data-cg-suggestions]")).to_be_hidden()
    expect(search).to_have_value("")


def test_search_clicking_suggestion_dismisses(page: Page, live_gallery):
    """Selecting a suggestion with the mouse must also reset the search UI."""
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    page.locator(".cg-sidebar__suggestion").first.click()
    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    expect(page.locator("[data-cg-suggestions]")).to_be_hidden()
    expect(search).to_have_value("")


def test_search_dedupes_recents_injected_links(page: Page, live_gallery):
    """Visiting a component adds it to Recents, which injects a *second*
    `<a data-cg-component>` into the sidebar. Search must dedupe by component
    so the dropdown shows one entry — not two — and the count stays honest.
    """
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    # SPA-navigate to button: records it in Recents AND fires
    # `cg-content-swapped`, which invalidates the search cache so the rebuild
    # picks up the injected duplicate link.
    page.locator("[data-cg-component='button']").first.click()
    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    suggestions = page.locator("[data-cg-suggestions]")
    expect(suggestions).to_be_visible()
    expect(suggestions.locator(".cg-sidebar__suggestion")).to_have_count(1)


# ── Keyboard navigation ──────────────────────────────────────────────────


def test_search_arrowdown_focuses_first_suggestion(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("t")  # matches both "button" and "input"
    expect(page.locator(".cg-sidebar__suggestion")).to_have_count(2)
    search.press("ArrowDown")
    expect(page.locator(".cg-sidebar__suggestion").first).to_be_focused()


def test_search_tab_autocompletes_and_collapses(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    search.press("Tab")
    # Tab completes the query to the first suggestion's full name in place,
    # then collapses the dropdown (accept-and-close, like attrs autocomplete).
    expect(search).to_have_value("button")
    expect(page.locator("[data-cg-suggestions]")).to_be_hidden()


def test_search_tab_then_enter_still_navigates(page: Page, live_gallery):
    """After Tab collapses the dropdown, Enter must still reach the match —
    it reads the (hidden) suggestion node rather than requiring a visible menu.
    """
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("but")
    search.press("Tab")
    expect(page.locator("[data-cg-suggestions]")).to_be_hidden()
    search.press("Enter")
    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/atoms/button/")


def test_search_arrowdown_reopens_after_tab_collapse(page: Page, live_gallery):
    """A Tab completion collapses the dropdown; ArrowDown must re-open it and
    dive into the list rather than staying dismissed."""
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("in")  # single match → "input"
    search.press("Tab")
    expect(page.locator("[data-cg-suggestions]")).to_be_hidden()
    search.press("ArrowDown")
    expect(page.locator("[data-cg-suggestions]")).to_be_visible()
    expect(page.locator(".cg-sidebar__suggestion").first).to_be_focused()


def test_search_arrowup_returns_focus_to_input(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("t")
    search.press("ArrowDown")  # into the dropdown
    page.keyboard.press("ArrowUp")  # back up off the top item
    expect(search).to_be_focused()


def test_search_enter_from_focused_suggestion_navigates(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    search = page.locator("[data-cg-search]")
    search.fill("in")  # matches "input"
    search.press("ArrowDown")  # focus the suggestion
    page.keyboard.press("Enter")  # activate the focused link
    expect(page).to_have_url(f"{live_gallery}/django-cotton-gallery/atoms/input/")
    expect(page.locator("[data-cg-suggestions]")).to_be_hidden()
