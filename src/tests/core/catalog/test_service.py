"""Tests for the CatalogService facade."""

from pathlib import Path

from django_cotton_gallery.core.catalog import CatalogService
from django_cotton_gallery.core.schemas import CatalogConfig


def test_get_catalog_returns_ordered(basic_config):
    service = CatalogService(basic_config)
    catalog = service.get_catalog()
    assert "atoms" in catalog
    assert "molecules" in catalog
    assert {c.name for c in catalog["atoms"][""]} == {"button", "input"}


def test_get_catalog_caches_result(basic_config, cotton_tree: Path):
    service = CatalogService(basic_config)
    first = service.get_catalog()
    second = service.get_catalog()
    assert first is second  # cache returns the exact same dict instance


def test_cache_invalidates_on_file_change(basic_config, cotton_tree: Path):
    import os

    service = CatalogService(basic_config)
    first = service.get_catalog()

    new_file = cotton_tree / "atoms" / "label.html"
    new_file.write_text("{# @description Label #}")
    # Bump mtime forward in case of fast filesystems.
    st = new_file.stat()
    os.utime(new_file, (st.st_atime, st.st_mtime + 5))

    second = service.get_catalog()
    assert first is not second
    assert {c.name for c in second["atoms"][""]} == {"button", "input", "label"}


def test_read_component_returns_path_tag_source(basic_config):
    service = CatalogService(basic_config)
    file, tag, source = service.read_component("atoms/button")
    assert file.name == "button.html"
    assert tag == "atoms.button"
    assert "Button" in source


def test_missing_cotton_dir_returns_empty(tmp_path: Path):
    config = CatalogConfig(cotton_dir=tmp_path / "missing")
    service = CatalogService(config)
    assert service.get_catalog() == {}
