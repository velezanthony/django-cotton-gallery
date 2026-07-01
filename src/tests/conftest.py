"""Top-level fixtures shared across multiple test modules."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.test.utils import override_settings

from django_cotton_gallery.factories import reset_caches


def _gallery_settings(templates_dir: Path) -> dict:
    """The TEMPLATES override block shared by gallery fixtures."""
    return {
        "TEMPLATES": [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [str(templates_dir)],
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
    }


@pytest.fixture
def gallery_empty_no_folder(tmp_path: Path):
    """Gallery setup where the cotton/ folder doesn't exist on disk.

    Used to exercise the "Cotton folder not found" branch of the index
    onboarding empty state.
    """
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    # No cotton/ subdir is created on purpose.
    with override_settings(**_gallery_settings(templates_dir)):
        reset_caches()
        yield templates_dir
        reset_caches()


@pytest.fixture
def gallery_empty_with_folder(tmp_path: Path):
    """Gallery setup where cotton/ exists but contains no components.

    Exercises the "No components yet" branch — the encouraging variant of
    the onboarding empty state.
    """
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "cotton").mkdir()
    with override_settings(**_gallery_settings(templates_dir)):
        reset_caches()
        yield templates_dir
        reset_caches()


@pytest.fixture
def gallery_setup(tmp_path: Path):
    """Build a minimal cotton/ tree and override Django settings to point at it.

    Yields the templates directory so tests can write more components if needed.
    Resets the factory caches before and after so per-test state is clean.
    """
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    cotton_dir = templates_dir / "cotton"
    cotton_dir.mkdir()
    atoms = cotton_dir / "atoms"
    atoms.mkdir()
    (atoms / "button.html").write_text(
        "{# @description Button #}\n"
        '{# @prop label:text | default:"Click" | description:"Label" #}\n'
        '<c-vars label="Click" />\n'
        "<button {{ attrs }}>{{ label }}</button>\n"
    )

    with override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [str(templates_dir)],
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
    ):
        reset_caches()
        yield templates_dir
        reset_caches()
