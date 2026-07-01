"""`python manage.py cotton_lint` — CI-friendly version of the lint report.

Walks the catalog, runs the linter, prints a coloured terminal report, and
exits 1 when any errors are found. Pass `--warnings-as-errors` to also fail
on warnings (useful for stricter CI policies).
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from django_cotton_gallery.core.linter import lint_catalog
from django_cotton_gallery.factories import get_catalog_service


# ANSI colour helpers — bypassed when stdout isn't a TTY (e.g. CI logs piped
# to a file) so the output stays parseable.
def _colorise(stream: Any) -> dict[str, str]:
    if not getattr(stream, "isatty", lambda: False)():
        return dict.fromkeys(("red", "yellow", "green", "dim", "bold", "reset"), "")
    return {
        "red": "\033[31m",
        "yellow": "\033[33m",
        "green": "\033[32m",
        "dim": "\033[2m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }


class Command(BaseCommand):
    help = "Lint @prop annotations against <c-vars> declarations across the catalog."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--warnings-as-errors",
            action="store_true",
            help="Exit non-zero when only warnings are found (no errors).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        c = _colorise(self.stdout)
        catalog = get_catalog_service()
        report = lint_catalog(catalog.sources())

        for cr in report.components:
            if cr.is_clean:
                continue
            self.stdout.write(f"\n{c['bold']}{cr.path}{c['reset']}")
            for issue in cr.issues:
                colour = c["red"] if issue.severity == "error" else c["yellow"]
                line = f"L{issue.line}" if issue.line else "  "
                self.stdout.write(
                    f"  {colour}{issue.severity:7}{c['reset']} "
                    f"{c['dim']}{line:>4} {issue.rule:28}{c['reset']} {issue.message}"
                )

        clean = report.clean_components
        total = len(report.components)
        self.stdout.write("")
        self.stdout.write(
            f"{c['green']}{clean}{c['reset']}/{total} clean · "
            f"{c['red']}{report.total_errors}{c['reset']} errors · "
            f"{c['yellow']}{report.total_warnings}{c['reset']} warnings"
        )

        failed = report.total_errors > 0 or (
            options["warnings_as_errors"] and report.total_warnings > 0
        )
        if failed:
            sys.exit(1)
