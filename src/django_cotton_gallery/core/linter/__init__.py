"""Annotation linter for Cotton components.

Cross-references the `@prop` comment annotations against the actual
`<c-vars>` declaration to enforce the documentation discipline of the
`django-cotton-props` extension. Pure — no I/O, no Django imports.

Severity tiers
--------------
- `error`   blocking issue, the prop won't reach the template as documented.
- `warning` style / discipline issue, fixable but real.
- `hint`    heuristic check that may produce false positives (e.g. a
            template variable that's actually injected by a custom context
            processor). The Insights health score weighs hints at 0 so
            third-party context doesn't drag the catalog grade down.

Rule catalog (severity in parens):

    missing-cvars           (warning)  Component has @prop but no <c-vars> tag.
    missing-annotation      (warning)  <c-vars> declares a prop with no @prop.
    orphan-annotation       (error)    @prop refers to a prop not in <c-vars>.
    dynamic-prefix-mismatch (error)    `:` prefix only on one side.
    default-mismatch        (error)    @prop default differs from <c-vars> value.
    required-with-default   (error)    `| required` but a default is present.
    enum-default-out-of-range (error)  default not listed in select['…'] options.
    type-default-mismatch   (error)    Default value doesn't match declared type.
    missing-description     (warning)  @prop without `| description`.
    undeclared-template-var (hint)     `{{ x }}` reference not in <c-vars>.
                                       Heuristic — context-processor vars
                                       and {% with %} locals will trip it.

This package was extracted from the original 530-line `linter.py` monolith
to make the rule loop, source-level scanners, and pure data types each
navigable in isolation. Public API below is unchanged — every external
import (`from .core.linter import ...`) continues to work.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..annotations import AnnotationParser
from ..cvars import parse_cvars
from ..schemas import ParsedComponent
from ._rules import lint_one
from ._scanners import (
    scan_required_with_default,
    scan_type_default_mismatch,
    scan_undeclared_template_vars,
)
from ._types import ComponentReport, LintIssue, LintReport, RuleCode, Severity

__all__ = [
    "ComponentReport",
    "LintIssue",
    "LintReport",
    "RuleCode",
    "Severity",
    "lint_catalog",
    "lint_component",
    "lint_summary",
]


def lint_component(
    component_path: str,
    source: str,
    *,
    parsed: ParsedComponent | None = None,
) -> ComponentReport:
    """Lint a single component's source. Public entry point used by view + CLI.

    Pass `parsed` when the caller has already parsed `source` (e.g. the
    insights view, which parses every component for its own metrics) to skip
    a redundant parse pass over the same catalog.
    """
    if parsed is None:
        parsed = AnnotationParser().parse(source)
    cvars = parse_cvars(source)
    issues = list(lint_one(component_path, parsed, cvars))
    issues.extend(scan_type_default_mismatch(component_path, source))
    issues.extend(scan_required_with_default(component_path, source))
    issues.extend(scan_undeclared_template_vars(component_path, source, cvars))
    return ComponentReport(path=component_path, issues=tuple(issues))


def lint_catalog(items: Iterable[tuple[str, str]]) -> LintReport:
    """Lint many components. `items` is an iterable of `(component_path, source)`."""
    reports = tuple(lint_component(p, s) for p, s in items)
    return LintReport(components=reports)


def lint_summary(items: Iterable[tuple[str, str]]) -> dict[str, tuple[int, int, int]]:
    """Per-component `(errors, warnings, hints)` count map for sidebar badges.

    Cheaper than `lint_catalog` when callers only need totals — skips the
    ComponentReport construction for issues with zero severity matches.
    Components with no issues across ALL severities are omitted so the
    template can use `{% if path in lint_summary %}` as a presence check.
    """
    summary: dict[str, tuple[int, int, int]] = {}
    for path, source in items:
        report = lint_component(path, source)
        errors = len(report.errors)
        warnings = len(report.warnings)
        hints = len(report.hints)
        if errors or warnings or hints:
            summary[path] = (errors, warnings, hints)
    return summary
