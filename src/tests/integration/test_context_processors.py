"""Tests for the gallery_assets context processor."""

from django.test.utils import override_settings

from django_cotton_gallery.context_processors import gallery_assets
from django_cotton_gallery.core.schemas import GalleryAssets


def test_empty_settings_returns_empty_assets():
    result = gallery_assets(request=None)
    assets = result["cotton_gallery"]
    assert isinstance(assets, GalleryAssets)
    assert assets.extra_css == ()
    assert assets.extra_js == ()
    assert assets.dependencies == ()


@override_settings(
    DJANGO_COTTON_GALLERY_EXTRA_CSS=["/static/app.css", "https://cdn.tailwindcss.com"],
    DJANGO_COTTON_GALLERY_EXTRA_JS=["https://unpkg.com/htmx.org@1.9"],
)
def test_populated_settings_propagate():
    assets = gallery_assets(request=None)["cotton_gallery"]
    assert assets.extra_css == ("/static/app.css", "https://cdn.tailwindcss.com")
    assert assets.extra_js == ("https://unpkg.com/htmx.org@1.9",)


@override_settings(
    DJANGO_COTTON_GALLERY_EXTRA_CSS=["https://cdn.tailwindcss.com"],
    DJANGO_COTTON_GALLERY_EXTRA_JS=["https://unpkg.com/htmx.org@1.9"],
)
def test_dependencies_detected_from_assets():
    assets = gallery_assets(request=None)["cotton_gallery"]
    names = {dep.name for dep in assets.dependencies}
    assert "tailwindcss" in names
    assert "htmx.org" in names
