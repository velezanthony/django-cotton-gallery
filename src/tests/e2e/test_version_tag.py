"""The sidebar version tag reports the installed distribution."""

from __future__ import annotations

from importlib.metadata import version

from playwright.sync_api import Page, expect


def test_sidebar_shows_the_installed_version(page: Page, live_gallery):
    """A literal in the template lies at every release; read it from the package."""
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    tag = page.locator(".cg-sidebar__footer-version-tag")

    expect(tag).to_have_text(f"v{version('django-cotton-gallery')}")
