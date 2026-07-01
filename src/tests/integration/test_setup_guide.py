"""Tests for the setup_guide first-run UX.

The gallery only blocks with the setup_guide when django-cotton itself
isn't installed. Anything else (TEMPLATES misconfiguration, DIRS empty,
missing context_processor) is part of cotton's own quickstart — we
trust cotton's docs to cover those, we don't reproduce them here.
"""

from __future__ import annotations

import builtins

import pytest
from django.urls import reverse


@pytest.fixture
def cotton_not_installed(monkeypatch):
    """Simulate `import django_cotton` failing (package missing)."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "django_cotton":
            raise ImportError("simulated: django_cotton not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_setup_guide_renders_when_cotton_missing(client, cotton_not_installed):
    """When django-cotton can't be imported, show the redirect page."""
    response = client.get(reverse("django_cotton_gallery:index"))
    assert response.status_code == 200
    assert b"django-cotton is not installed" in response.content
    assert b"https://django-cotton.com/docs/quickstart" in response.content
    # We must NOT have raised ImproperlyConfigured (that would 500).
    assert b"ImproperlyConfigured" not in response.content


def test_index_loads_normally_when_cotton_is_installed(client, gallery_setup):
    """Cotton installed + properly wired -> normal index, no setup_guide."""
    response = client.get(reverse("django_cotton_gallery:index"))
    assert response.status_code == 200
    assert b"Welcome \xe2\x80\x94 let" not in response.content  # the hero title
    assert b"django-cotton is not installed" not in response.content


def test_cotton_folder_missing_uses_index_empty_state(client, gallery_empty_no_folder):
    """Cotton installed, settings wired, but the templates/cotton/ folder
    doesn't exist yet -> the index's own onboarding empty state takes over.
    The setup_guide is reserved for "cotton not installed".
    """
    response = client.get(reverse("django_cotton_gallery:index"))
    assert response.status_code == 200
    assert b"Cotton folder not found" in response.content
    assert b"django-cotton is not installed" not in response.content


def test_setup_guide_has_theme_toggle_and_language_switch(client, cotton_not_installed):
    """The setup page must include UI for both — they're standalone."""
    response = client.get(reverse("django_cotton_gallery:index"))
    body = response.content
    assert b'id="theme-toggle"' in body
    assert b'id="lang-trigger"' in body
    assert b'id="lang-menu"' in body


def test_setup_guide_lang_param_activates_locale(client, cotton_not_installed):
    """?lang=es should switch the active locale, reflected in <html lang>."""
    response = client.get(reverse("django_cotton_gallery:index") + "?lang=es")
    assert b'<html lang="es"' in response.content


def test_setup_guide_ignores_invalid_lang(client, cotton_not_installed):
    """Unknown ?lang= should fall back silently, not crash."""
    response = client.get(reverse("django_cotton_gallery:index") + "?lang=zzz")
    assert response.status_code == 200
    assert b'<html lang="zzz"' not in response.content


def test_index_renders_without_i18n_urls_mounted(client, gallery_setup):
    """Bug repro: the consumer hadn't mounted django.conf.urls.i18n,
    so `{% url 'set_language' %}` in base.html exploded the index
    page with NoReverseMatch — even though the gallery itself does
    not strictly need i18n URLs to function.

    The fix: the language switcher is conditional on `set_language`
    being resolvable. When it's not, the switcher is hidden and the
    page renders normally in the active locale.
    """
    from django.test.utils import override_settings

    with override_settings(ROOT_URLCONF="tests.urls_no_i18n"):
        # The gallery is mounted under /django-cotton-gallery/ via
        # django_cotton_gallery.urls — same as the default test urlconf,
        # just without the i18n include.
        response = client.get("/django-cotton-gallery/")
    assert response.status_code == 200
    # Template renders without the <form> tag of the language switcher.
    assert b'class="cg-sidebar__lang"' not in response.content


def test_setup_guide_offers_only_four_languages(client, cotton_not_installed):
    """The dropdown is hardcoded to en/es/eu/fr — independent of the
    consumer's LANGUAGES setting.
    """
    response = client.get(reverse("django_cotton_gallery:index"))
    body = response.content.decode("utf-8")
    assert 'data-lang="en"' in body
    assert 'data-lang="es"' in body
    assert 'data-lang="eu"' in body
    assert 'data-lang="fr"' in body
    # No accidental fifth language.
    assert body.count('data-lang="') == 4
