"""Sanity checks that the package imports and Django picks up the app config."""

from importlib.metadata import version

import django_cotton_gallery


def test_version_matches_the_distribution():
    """A literal here would just pin whatever drifted. Compare the two."""
    assert django_cotton_gallery.__version__ == version("django-cotton-gallery")


def test_app_config_loaded():
    from django.apps import apps

    config = apps.get_app_config("django_cotton_gallery")
    assert config.name == "django_cotton_gallery"
    assert config.verbose_name == "Django Cotton Gallery"
