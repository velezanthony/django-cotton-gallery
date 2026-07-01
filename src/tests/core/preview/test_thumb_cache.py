"""Tests for the thumbnail cache."""

from django_cotton_gallery.core.preview.thumb_cache import ThumbCache


def test_empty_returns_none():
    cache = ThumbCache()
    assert cache.get("atoms.button", 100.0) is None


def test_set_and_get():
    cache = ThumbCache()
    cache.set("atoms.button", 100.0, "<html />")
    assert cache.get("atoms.button", 100.0) == "<html />"


def test_different_mtime_misses():
    cache = ThumbCache()
    cache.set("atoms.button", 100.0, "<old />")
    assert cache.get("atoms.button", 200.0) is None


def test_different_key_misses():
    cache = ThumbCache()
    cache.set("atoms.button", 100.0, "<x />")
    assert cache.get("atoms.input", 100.0) is None


def test_set_overwrites():
    cache = ThumbCache()
    cache.set("atoms.button", 100.0, "<v1 />")
    cache.set("atoms.button", 200.0, "<v2 />")
    assert cache.get("atoms.button", 200.0) == "<v2 />"
    assert cache.get("atoms.button", 100.0) is None


def test_clear_empties_all():
    cache = ThumbCache()
    cache.set("a", 1.0, "x")
    cache.set("b", 2.0, "y")
    cache.clear()
    assert cache.get("a", 1.0) is None
    assert cache.get("b", 2.0) is None
