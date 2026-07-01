"""Per-component thumbnail cache with mtime-based invalidation."""

from __future__ import annotations


class ThumbCache:
    """Stores rendered thumbnail HTML keyed by component path + file mtime."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, str]] = {}

    def get(self, key: str, mtime: float) -> str | None:
        entry = self._entries.get(key)
        if entry is None or entry[0] != mtime:
            return None
        return entry[1]

    def set(self, key: str, mtime: float, html: str) -> None:
        self._entries[key] = (mtime, html)

    def clear(self) -> None:
        self._entries.clear()
