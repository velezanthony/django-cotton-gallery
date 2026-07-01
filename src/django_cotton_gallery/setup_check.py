"""Detect whether django-cotton is installed so the gallery can render
a friendly redirect page instead of crashing.

Single check: is the django-cotton Python package importable?

Rationale: if the user followed cotton's quickstart
(https://django-cotton.com/docs/quickstart), the rest of the Django
config (INSTALLED_APPS, TEMPLATES, DIRS) is already correct — those
steps ARE the quickstart. Anything else that fails afterwards is the
user not following cotton's setup, which cotton's docs cover better
than we ever could.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from django.utils.translation import gettext_lazy as _

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class SetupIssue:
    id: str
    severity: Severity
    title: str
    description: str
    fix_label: str
    fix_code: str
    link: str | None = None


def check_setup() -> list[SetupIssue]:
    if _is_cotton_installed():
        return []
    return [
        SetupIssue(
            id="cotton-not-installed",
            severity="error",
            title=str(_("django-cotton is not installed")),
            description=str(
                _(
                    "django-cotton-gallery is built on top of django-cotton. "
                    "Install and configure cotton in your Django project, then "
                    "refresh this page. The cotton quickstart walks you through "
                    "the install, INSTALLED_APPS entry, and template loader "
                    "setup in a few steps."
                )
            ),
            fix_label=str(_("Open the cotton quickstart")),
            fix_code="",
            link="https://django-cotton.com/docs/quickstart",
        )
    ]


def has_blocking_errors(issues: list[SetupIssue]) -> bool:
    return any(i.severity == "error" for i in issues)


def _is_cotton_installed() -> bool:
    try:
        import django_cotton  # noqa: F401
    except ImportError:
        return False
    return True
