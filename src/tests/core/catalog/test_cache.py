"""Tests for the single-slot CatalogCache container."""

from django_cotton_gallery.core.catalog.cache import CatalogCache


def test_empty_is_not_fresh():
    cache: CatalogCache[str] = CatalogCache()
    assert cache.is_fresh((1, 2.0)) is False
    assert cache.get() is None


def test_set_and_retrieve():
    cache: CatalogCache[str] = CatalogCache()
    cache.set((3, 100.0), "payload")
    assert cache.is_fresh((3, 100.0)) is True
    assert cache.get() == "payload"


def test_different_signature_is_not_fresh():
    cache: CatalogCache[str] = CatalogCache()
    cache.set((3, 100.0), "old")
    assert cache.is_fresh((4, 100.0)) is False


def test_clear_resets():
    cache: CatalogCache[str] = CatalogCache()
    cache.set((1, 1.0), "x")
    cache.clear()
    assert cache.get() is None
    assert cache.is_fresh((1, 1.0)) is False
