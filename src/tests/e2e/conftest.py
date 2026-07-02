"""End-to-end test fixtures.

Spins up a Django live server with the cotton gallery wired up, then drives
it through Playwright. Browser launches headless by default; pass
`--headed` on the pytest CLI to watch tests run interactively.
"""

from __future__ import annotations

import os

# Playwright spawns its event loop on a worker thread; Django's async-context
# guard in `connection.close()` raises SynchronousOnlyOperation when the
# fixture chain crosses that thread. Setting this BEFORE any django imports
# makes the guard a no-op — safe in tests because we own the event loop.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

from pathlib import Path

import pytest

from django_cotton_gallery.factories import reset_caches


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Reasonable defaults for the browser context.

    Clipboard permissions are granted so the copy/share buttons
    (`navigator.clipboard.writeText`) can be asserted by reading the
    clipboard back — otherwise chromium blocks the read in headless runs.
    """
    return {
        **browser_context_args,
        "viewport": {"width": 1600, "height": 1000},
        "ignore_https_errors": True,
        "permissions": ["clipboard-read", "clipboard-write"],
    }


@pytest.fixture
def cotton_tree(tmp_path: Path) -> Path:
    """Build a small cotton/ tree with annotated components for E2E flows."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    cotton_dir = templates_dir / "cotton"
    cotton_dir.mkdir()
    atoms = cotton_dir / "atoms"
    atoms.mkdir()
    (atoms / "button.html").write_text(
        "{# @description Primary action button #}\n"
        "{# @prop variant:select['primary', 'secondary', 'danger'] | default:\"primary\" | description:\"Style\" #}\n"
        '{# @prop loading:boolean | default:False | description:"Show spinner" #}\n'
        '<c-vars variant="primary" loading=False />\n'
        '<button class="btn btn-{{ variant }}" {{ attrs }}>{{ slot }}</button>\n'
    )
    (atoms / "input.html").write_text(
        "{# @description Text input #}\n"
        '{# @prop label:text | default:"" #}\n'
        '<c-vars label="" />\n'
        "<label>{{ label }}<input {{ attrs }}></label>\n"
    )
    return templates_dir


@pytest.fixture
def live_gallery(transactional_db, live_server, cotton_tree, settings):
    """Live Django server with the gallery rendering the temp cotton/ tree.

    Returns the base URL of the live server, e.g. http://localhost:NNNNN.
    Override `TEMPLATES` so the gallery scans our temp tree, then reset the
    factory caches so the new config is picked up. Yields the URL.
    """
    settings.TEMPLATES = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [str(cotton_tree)],
            "APP_DIRS": False,
            "OPTIONS": {
                "loaders": [
                    (
                        "django.template.loaders.cached.Loader",
                        [
                            "django_cotton.cotton_loader.Loader",
                            "django.template.loaders.filesystem.Loader",
                            "django.template.loaders.app_directories.Loader",
                        ],
                    )
                ],
                "builtins": ["django_cotton.templatetags.cotton"],
                "context_processors": [
                    "django.template.context_processors.request",
                    "django_cotton_gallery.context_processors.gallery_assets",
                ],
            },
        }
    ]
    reset_caches()
    yield live_server.url
    reset_caches()
