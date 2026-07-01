"""Tests for the dev-only-tool warning emitted by AppConfig.ready().

The library never reads DEBUG nor any flag of its own. The warning fires
exactly when the gallery URLs are actually mounted in this process — we
detect that via reverse(). Mounting is the consumer's call: they wrap the
URL include in whatever `if` they want.
"""

from __future__ import annotations

import warnings

from django.test.utils import override_settings

from django_cotton_gallery.apps import DjangoCottonGalleryConfig


def _ready_and_collect_warnings() -> list[warnings.WarningMessage]:
    """Manually invoke ready() and capture any RuntimeWarning it emits."""
    config = DjangoCottonGalleryConfig.create("django_cotton_gallery")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        config.ready()
    return [w for w in caught if issubclass(w.category, RuntimeWarning)]


def test_warns_when_gallery_urls_are_mounted():
    # Default tests/urls.py mounts the gallery → reverse() succeeds → warn.
    warns = _ready_and_collect_warnings()
    assert len(warns) == 1
    assert "MOUNTED AND SERVING" in str(warns[0].message)


@override_settings(ROOT_URLCONF="tests.urls_unmounted")
def test_silent_when_gallery_urls_are_not_mounted():
    # urls_unmounted.py has urlpatterns = [] → reverse() raises NoReverseMatch.
    warns = _ready_and_collect_warnings()
    assert warns == [], f"Expected silence when not mounted, got: {[str(w.message) for w in warns]}"


def test_silent_in_runserver_parent_process(monkeypatch):
    # The autoreloader spawns parent + child; the parent has RUN_MAIN unset.
    # We want the child to warn (it's the real server) and the parent to stay
    # silent so the warning isn't duplicated.
    monkeypatch.setattr("sys.argv", ["manage.py", "runserver"])
    monkeypatch.delenv("RUN_MAIN", raising=False)
    warns = _ready_and_collect_warnings()
    assert warns == []


def test_warns_in_runserver_child_process(monkeypatch):
    monkeypatch.setattr("sys.argv", ["manage.py", "runserver"])
    monkeypatch.setenv("RUN_MAIN", "true")
    warns = _ready_and_collect_warnings()
    assert len(warns) == 1
