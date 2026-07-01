"""Catalog cache — single-slot container keyed on a (count, mtime) signature."""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class CatalogCache(Generic[T]):
    """Holds one cached value plus the signature it was computed with.

    Usage:
        cache = CatalogCache[Catalog]()
        sig = signature(config)
        if not cache.is_fresh(sig):
            cache.set(sig, build_catalog(config))
        return cache.get()
    """

    def __init__(self) -> None:
        self._signature: tuple | None = None
        self._value: T | None = None

    def is_fresh(self, signature: tuple) -> bool:
        return self._signature is not None and self._signature == signature

    def get(self) -> T | None:
        return self._value

    def set(self, signature: tuple, value: T) -> None:
        self._signature = signature
        self._value = value

    def clear(self) -> None:
        self._signature = None
        self._value = None
