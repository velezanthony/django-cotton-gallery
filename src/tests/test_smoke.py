"""Sanity checks that the package imports and Django picks up the app config."""

import django_cotton_gallery


def test_version_exposed():
    assert django_cotton_gallery.__version__ == "0.1.0"


def test_app_config_loaded():
    from django.apps import apps

    config = apps.get_app_config("django_cotton_gallery")
    assert config.name == "django_cotton_gallery"
    assert config.verbose_name == "Django Cotton Gallery"
