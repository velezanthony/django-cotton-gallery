"""Integration tests for PreviewService — exercises the full Cotton + Django render path."""

import pytest
from django.http import HttpRequest

from django_cotton_gallery.core.preview import PreviewService, ThumbCache
from django_cotton_gallery.core.schemas import ParsedComponent, Prop

pytestmark = pytest.mark.django_db


@pytest.fixture
def request_obj():
    req = HttpRequest()
    req.method = "GET"
    return req


def test_render_live_returns_html_and_cotton_str(request_obj):
    service = PreviewService()
    parsed = ParsedComponent(
        props=(Prop(name="x", clean_name="x", type="text"),),
    )
    html, cotton_str = service.render_live(request_obj, "atoms.unknown", parsed, {})
    assert isinstance(html, str)
    assert "c-atoms.unknown" in cotton_str


def test_render_thumb_caches(request_obj):
    cache = ThumbCache()
    service = PreviewService(thumb_cache=cache)
    parsed = ParsedComponent()
    a = service.render_thumb(request_obj, "atoms.x", parsed, 100.0)
    b = service.render_thumb(request_obj, "atoms.x", parsed, 100.0)
    assert a == b
    # Cache was hit on the second call.
    assert cache.get("atoms.x", 100.0) is not None


def test_render_thumb_invalidates_on_mtime_change(request_obj):
    cache = ThumbCache()
    service = PreviewService(thumb_cache=cache)
    parsed = ParsedComponent()
    service.render_thumb(request_obj, "atoms.x", parsed, 100.0)
    service.render_thumb(request_obj, "atoms.x", parsed, 200.0)
    # Old entry replaced.
    assert cache.get("atoms.x", 100.0) is None
    assert cache.get("atoms.x", 200.0) is not None
