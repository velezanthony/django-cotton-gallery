"""Tests for the lru_cache-based service factories."""

from django_cotton_gallery.factories import (
    get_catalog_config,
    get_catalog_service,
    get_parser,
    get_preview_service,
    reset_caches,
)


def test_parser_returns_same_instance():
    a = get_parser()
    b = get_parser()
    assert a is b


def test_preview_service_returns_same_instance():
    assert get_preview_service() is get_preview_service()


def test_reset_caches_yields_new_parser():
    a = get_parser()
    reset_caches()
    b = get_parser()
    assert a is not b


def test_catalog_config_reads_settings(gallery_setup):
    config = get_catalog_config()
    assert config.cotton_dir == gallery_setup / "cotton"


def test_catalog_service_uses_config(gallery_setup):
    service = get_catalog_service()
    assert service.config.cotton_dir == gallery_setup / "cotton"


def test_catalog_service_returns_same_instance(gallery_setup):
    assert get_catalog_service() is get_catalog_service()
