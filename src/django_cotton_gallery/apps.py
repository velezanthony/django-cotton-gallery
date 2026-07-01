"""AppConfig — emits a dev-only-tool warning when the gallery is mounted.

The gallery is a development tool. Its endpoints evaluate `request.GET` params
through the Django template engine and expose component source code. None of
that is appropriate to ship to production.

We can't *force* the consumer to keep the gallery off in production — they own
their URL config — but we CAN detect whether the gallery URLs are actually
mounted in this process (via `reverse()`) and emit a `RuntimeWarning` so the
situation is loud whenever the gallery is wired.

The library never reads `DEBUG` nor any flag of its own. Mounting is 100% the
consumer's decision: they wrap the URL include in their own `if` (DEBUG, a
custom flag, an env var — whatever). The presence of mounted URLs is the only
signal we use.
"""

from __future__ import annotations

import os
import sys
import warnings

from django.apps import AppConfig


def _build_dev_only_warning() -> str:
    use_color = sys.stderr.isatty() and "NO_COLOR" not in os.environ
    if use_color:
        bold = "\033[1m"
        red = "\033[91m"
        yellow = "\033[93m"
        dim = "\033[2m"
        reset = "\033[0m"
    else:
        bold = red = yellow = dim = reset = ""

    return (
        f"\n\n"
        f"  {red}{bold}╔══════════════════════════════════════════════════════════════════╗{reset}\n"
        f"  {red}{bold}║  django-cotton-gallery is MOUNTED AND SERVING                    ║{reset}\n"
        f"  {red}{bold}╚══════════════════════════════════════════════════════════════════╝{reset}\n"
        f"\n"
        f"  {yellow}{bold}This is a DEVELOPMENT tool.{reset}\n"
        f"\n"
        f"  Its endpoints:\n"
        f"    • Evaluate URL params through the Django template engine.\n"
        f"    • Expose component source code.\n"
        f"\n"
        f"  {red}{bold}Do NOT expose its URLs in production.{reset}\n"
        f"\n"
        f"  {dim}To silence this warning:{reset}\n"
        f"    • Wrap the gallery URL include in your urls.py with an `if`\n"
        f"      that you control (e.g. `if settings.DEBUG:` or your own flag).\n"
    )


class DjangoCottonGalleryConfig(AppConfig):
    name = "django_cotton_gallery"
    verbose_name = "Django Cotton Gallery"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Django's `runserver` autoreloader spawns parent + child processes;
        # both run AppConfig.ready() and would emit the warning twice.
        # The child has `RUN_MAIN=true`; the parent does not.
        is_runserver_parent = "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true"
        if is_runserver_parent:
            return

        # Only warn when the gallery URLs are actually wired in this process.
        # If the consumer's `if` is False, the include is skipped, reverse()
        # raises NoReverseMatch and we stay silent.
        from django.urls import NoReverseMatch, reverse

        try:
            reverse("django_cotton_gallery:index")
        except NoReverseMatch:
            return

        warnings.warn(_build_dev_only_warning(), RuntimeWarning, stacklevel=2)
