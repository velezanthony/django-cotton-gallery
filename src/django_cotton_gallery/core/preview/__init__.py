"""Preview subpackage — tag composition, Cotton+Django rendering, thumbnail caching.

The `PreviewService` facade composes the units. Build it via the factories
layer so views inject a single instance.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.http import HttpRequest

from ..schemas import ParsedComponent
from .renderer import render as _render
from .sanitizer import sanitize_extra_attrs
from .tag_builder import build_default_tag, build_tag
from .thumb_cache import ThumbCache

__all__ = [
    "PreviewService",
    "ThumbCache",
    "build_default_tag",
    "build_tag",
    "sanitize_extra_attrs",
]


class PreviewService:
    """Orchestrates building a Cotton tag and rendering it via Django."""

    def __init__(self, thumb_cache: ThumbCache | None = None) -> None:
        self._thumb_cache = thumb_cache or ThumbCache()

    def render_live(
        self,
        request: HttpRequest,
        tag_path: str,
        parsed: ParsedComponent,
        params: Mapping[str, str],
    ) -> tuple[str, str]:
        """Return (rendered_html, cotton_tag_str) for the live preview pane."""
        cotton_str = build_tag(tag_path, parsed, params)
        return _render(request, cotton_str), cotton_str

    def render_thumb(
        self,
        request: HttpRequest,
        tag_path: str,
        parsed: ParsedComponent,
        mtime: float,
    ) -> str:
        """Return cached or freshly rendered default-prop thumbnail HTML."""
        cached = self._thumb_cache.get(tag_path, mtime)
        if cached is not None:
            return cached
        html = _render(request, build_default_tag(tag_path, parsed))
        self._thumb_cache.set(tag_path, mtime, html)
        return html
