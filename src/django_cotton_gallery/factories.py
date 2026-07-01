"""Service factories — single point of truth for building Catalog/Preview/Parser.

Replaces the lazy module-level singleton anti-pattern. Each builder is
`lru_cache`-d so repeat calls return the same instance, but `cache_clear()`
makes per-test overrides trivial — including with `@override_settings`.

Setting names and defaults live in `conf.py`; this module only orchestrates
service construction.
"""

from __future__ import annotations

from functools import lru_cache

from .conf import load, resolve_cotton_dir
from .core.annotations import AnnotationParser
from .core.catalog import CatalogService
from .core.preview import PreviewService
from .core.schemas import CatalogConfig


@lru_cache(maxsize=1)
def get_catalog_config() -> CatalogConfig:
    """Build an immutable CatalogConfig from the typed settings snapshot."""
    s = load()
    return CatalogConfig(
        cotton_dir=resolve_cotton_dir(s),
        excluded_categories=s.excluded_categories,
        category_order=s.category_order,
        category_sort=s.category_sort,
        subcategory_order=s.subcategory_order,
        subcategory_sort=s.subcategory_sort,
    )


@lru_cache(maxsize=1)
def get_parser() -> AnnotationParser:
    return AnnotationParser()


@lru_cache(maxsize=1)
def get_catalog_service() -> CatalogService:
    return CatalogService(get_catalog_config(), get_parser())


@lru_cache(maxsize=1)
def get_preview_service() -> PreviewService:
    return PreviewService()


def reset_caches() -> None:
    """Clear every cached factory — for tests using @override_settings."""
    get_catalog_config.cache_clear()
    get_parser.cache_clear()
    get_catalog_service.cache_clear()
    get_preview_service.cache_clear()
