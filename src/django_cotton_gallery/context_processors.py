"""Expose consumer-injected gallery assets to every gallery template.

Reads the typed `GallerySettings` snapshot from `conf.load()` and detects
frontend dependencies (Tailwind, HTMX, Alpine, …) from the asset URLs.

Also exposes `gallery_languages`: the locales the package ships
translations for. The dropdown always offers the package's full set
of translations regardless of the consumer's `LANGUAGES` setting —
the gallery is a library that brings its own translations, the user
should be able to use them.

Caveat: Django's LocaleMiddleware only persists language switches
when the chosen code is in `settings.LANGUAGES`. The default
`LANGUAGES` (when the consumer hasn't set it explicitly) contains all
~80 locales Django knows about, so en/es/eu/fr are all there and
work without any further config. Consumers with a RESTRICTED
`LANGUAGES` setting need to add the four codes themselves — covered
in `getting-started.md` step 7.
"""

from __future__ import annotations

from django.http import HttpRequest

from .conf import load
from .core.dependencies import detect as detect_dependencies
from .core.schemas import GalleryAssets

CONTEXT_KEY = "cotton_gallery"

# Locales the package ships translations for. Keep in sync with
# src/django_cotton_gallery/locale/<code>/LC_MESSAGES/django.po —
# adding a `.po` file alone won't expand the dropdown; this tuple is
# the source of truth for what the UI surfaces.
PACKAGE_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("es", "Español"),
    ("eu", "Euskara"),
    ("fr", "Français"),
)


def gallery_assets(request: HttpRequest) -> dict:
    s = load()
    return {
        CONTEXT_KEY: GalleryAssets(
            extra_css=s.extra_css,
            extra_js=s.extra_js,
            dependencies=detect_dependencies(s.extra_css + s.extra_js),
        ),
        "gallery_languages": PACKAGE_LANGUAGES,
    }
