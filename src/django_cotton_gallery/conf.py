"""Typed access to Django settings consumed by the gallery.

`GallerySettings` is a frozen dataclass with sensible defaults; `load()` reads
each `getattr(settings, ...)` once and returns a typed snapshot. Centralising
the setting-name strings here means there is exactly ONE place that names them
and exactly ONE place that resolves their defaults.

`load()` is intentionally cheap: it does NOT touch `settings.TEMPLATES` (which
is only needed by the catalog scanner). Resolving the cotton/ directory path
is a separate step — call `resolve_cotton_dir(settings)` on demand. This keeps
the asset-side context processor working in test setups that don't configure
TEMPLATES.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from django.apps import apps
from django.conf import settings

# ── Setting names — single source of truth ──────────────────────────────────
SETTING_COTTON_DIR = "COTTON_DIR"
SETTING_EXCLUDED_CATEGORIES = "DJANGO_COTTON_GALLERY_EXCLUDED_CATEGORIES"
SETTING_CATEGORY_ORDER = "DJANGO_COTTON_GALLERY_CATEGORY_ORDER"
SETTING_CATEGORY_SORT = "DJANGO_COTTON_GALLERY_CATEGORY_SORT"
SETTING_SUBCATEGORY_ORDER = "DJANGO_COTTON_GALLERY_SUBCATEGORY_ORDER"
SETTING_SUBCATEGORY_SORT = "DJANGO_COTTON_GALLERY_SUBCATEGORY_SORT"
SETTING_EXTRA_CSS = "DJANGO_COTTON_GALLERY_EXTRA_CSS"
SETTING_EXTRA_JS = "DJANGO_COTTON_GALLERY_EXTRA_JS"
SETTING_SCAN_EXTERNAL_USERS = "DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS"

DEFAULT_COTTON_SUBFOLDER = "cotton"

SortMode = Literal["asc", "desc"]


@dataclass(frozen=True)
class GallerySettings:
    """Snapshot of every Django setting the gallery reads.

    `cotton_subfolder` is the raw subfolder name (default `"cotton"`); the
    absolute filesystem path is resolved on demand by `resolve_cotton_dir()`.
    """

    cotton_subfolder: str = DEFAULT_COTTON_SUBFOLDER
    excluded_categories: frozenset[str] = field(default_factory=frozenset)
    category_order: tuple[str, ...] = ()
    category_sort: SortMode = "asc"
    subcategory_order: dict[str, tuple[str, ...]] = field(default_factory=dict)
    subcategory_sort: SortMode = "asc"
    extra_css: tuple[str, ...] = ()
    extra_js: tuple[str, ...] = ()
    # Opt-in scanning of consumer templates (TEMPLATES.DIRS + each app's
    # templates/) to discover external references to catalog components.
    # Default `False` — the gallery only reads the consumer's codebase when
    # they explicitly ask. When enabled, the detail page lists templates
    # that import each component and the Insights dashboard can compute
    # zombie / most-referenced metrics. Read-only, dev-only, paths-only
    # exposure (no template content is rendered in the gallery UI).
    scan_external_users: bool = False


def load() -> GallerySettings:
    """Read every relevant Django setting once and return a typed snapshot.

    Does NOT resolve `settings.TEMPLATES`. Catalog consumers that need the
    absolute `cotton/` path should call `resolve_cotton_dir(settings)`.
    """
    return GallerySettings(
        cotton_subfolder=getattr(settings, SETTING_COTTON_DIR, DEFAULT_COTTON_SUBFOLDER),
        excluded_categories=frozenset(getattr(settings, SETTING_EXCLUDED_CATEGORIES, ())),
        category_order=tuple(getattr(settings, SETTING_CATEGORY_ORDER, ())),
        category_sort=getattr(settings, SETTING_CATEGORY_SORT, "asc"),
        subcategory_order={
            k: tuple(v) for k, v in getattr(settings, SETTING_SUBCATEGORY_ORDER, {}).items()
        },
        subcategory_sort=getattr(settings, SETTING_SUBCATEGORY_SORT, "asc"),
        extra_css=tuple(getattr(settings, SETTING_EXTRA_CSS, ())),
        extra_js=tuple(getattr(settings, SETTING_EXTRA_JS, ())),
        scan_external_users=bool(getattr(settings, SETTING_SCAN_EXTERNAL_USERS, False)),
    )


def resolve_cotton_dir(s: GallerySettings) -> Path:
    """Resolve the absolute path to the cotton/ folder the gallery scans.

    Walks every template root Django would resolve from — both project
    `TEMPLATES[*]['DIRS']` and `<app>/templates/` for installed apps
    when `app_directories.Loader` is in use — and picks the first
    location that contains the cotton subfolder. Mirrors how cotton
    itself locates components, so cotton's automatic and custom
    setup modes both work transparently.

    When no cotton/ folder exists anywhere yet, returns a sensible
    default path the user can create. Never raises: the catalog
    scanner tolerates non-existent paths and the index empty state
    surfaces the missing directory with copy-pasteable instructions.
    """
    roots = discover_template_roots()
    for root in roots:
        candidate = root / s.cotton_subfolder
        if candidate.is_dir():
            return candidate
    if roots:
        return roots[0] / s.cotton_subfolder
    # No template roots at all (consumer's TEMPLATES is empty or
    # malformed). Return a relative placeholder; the index empty
    # state will flag it as missing with the absolute resolved path.
    return Path("templates") / s.cotton_subfolder


def discover_template_roots() -> list[Path]:
    """Return every directory Django would resolve a template from.

    Combines `settings.TEMPLATES[*]['DIRS']` (project-level) with each
    installed app's `templates/` subfolder (when present and the
    `app_directories.Loader` is in use, which it is by default for
    Django Templates backends without `'APP_DIRS': False`).

    Used by the optional external-references scan — see
    `DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS`. Only invoked when the consumer
    has explicitly opted in to scanning their codebase.
    """
    roots: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        try:
            resolved = p.resolve()
        except OSError:
            return
        if resolved in seen:
            return
        seen.add(resolved)
        roots.append(resolved)

    for backend in getattr(settings, "TEMPLATES", []) or []:
        if not isinstance(backend, dict):
            continue
        for d in backend.get("DIRS", ()) or ():
            add(Path(d))
        # Only include app templates when the backend actually loads them.
        # `APP_DIRS=True` (or the absence of an explicit False) and the
        # `app_directories.Loader` both signal that.
        app_dirs_enabled = backend.get("APP_DIRS", True)
        loaders = (backend.get("OPTIONS") or {}).get("loaders") or ()

        def _has_app_loader(
            items: Iterable[Any],
        ) -> bool:  # nested traverse — loaders can be cached
            for item in items:
                if isinstance(item, str):
                    if "app_directories" in item:
                        return True
                elif (
                    isinstance(item, (list, tuple)) and len(item) >= 2 and _has_app_loader(item[1:])
                ):
                    return True
            return False

        if app_dirs_enabled or (loaders and _has_app_loader(loaders)):
            for app_config in apps.get_app_configs():
                app_templates = Path(app_config.path) / "templates"
                if app_templates.is_dir():
                    add(app_templates)

    return roots
