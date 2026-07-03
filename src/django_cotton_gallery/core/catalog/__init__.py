"""Catalog subpackage — discovery, resolution, ordering, caching.

The `CatalogService` facade composes the four units. Build it via the
factories layer (`factories.build_catalog_service`) so Django settings
stay out of the domain.
"""

from __future__ import annotations

from pathlib import Path

from ..annotations import AnnotationParser
from ..schemas import Catalog, CatalogConfig
from ..source_reader import read_text
from .cache import CatalogCache
from .orderer import order_catalog
from .resolver import ComponentNotFound, resolve
from .scanner import clear_signature_cache, group_by_category, scan, signature

__all__ = [
    "CatalogCache",
    "CatalogService",
    "ComponentNotFound",
    "clear_signature_cache",
    "group_by_category",
    "order_catalog",
    "resolve",
    "scan",
    "signature",
]


class CatalogService:
    """Orchestrates scanning, ordering, and caching the component catalog."""

    def __init__(
        self,
        config: CatalogConfig,
        parser: AnnotationParser | None = None,
        cache: CatalogCache[Catalog] | None = None,
    ) -> None:
        self.config = config
        self.parser = parser or AnnotationParser()
        self._cache: CatalogCache[Catalog] = cache or CatalogCache()

    def get_catalog(self) -> Catalog:
        """Return the ordered catalog. Cached until the signature changes."""
        sig = signature(self.config)
        if self._cache.is_fresh(sig):
            cached = self._cache.get()
            if cached is not None:
                return cached
        components = list(scan(self.config, self.parser))
        ordered = order_catalog(group_by_category(components), self.config)
        self._cache.set(sig, ordered)
        return ordered

    def read_component(self, component_path: str) -> tuple[Path, str, str]:
        """Resolve + read a component. Returns (file_path, tag_path, source)."""
        file, tag_path = resolve(self.config.cotton_dir, component_path)
        return file, tag_path, read_text(file)

    def sources(self) -> list[tuple[str, str]]:
        """Every component as `(path, source)` pairs, in catalog order.

        Shared by catalog-wide features (lint catalog, insights, component
        graph). `scan()` already populates `Component.source` during the walk,
        and the cache invalidates when any file's mtime changes — so reading
        `comp.source` is both correct and free, instead of round-tripping
        through `read_component()` (resolve + read per file = ~50 ms wasted on
        a 100-component catalog per request).
        """
        return [
            (comp.path, comp.source)
            for subcats in self.get_catalog().values()
            for components in subcats.values()
            for comp in components
        ]
