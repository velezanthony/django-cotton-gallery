"""LintIssue + ComponentReport + LintReport — pure data, no logic.

Split out so the scanners and rule helpers can import without pulling
in the rest of the linter machinery, and so the public API in
`__init__.py` stays small and easy to read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning", "hint"]

# The single source of truth for valid lint rule codes. Producers (the rule
# helpers and source scanners) and the consumer (`_LINT_MESSAGES` in the
# template tags) are both checked against this Literal, so a typo on either
# side — or a code with no registered message template — is a mypy error
# rather than a silent fallback to the English log message.
RuleCode = Literal[
    "missing-cvars",
    "missing-annotation",
    "orphan-annotation",
    "dynamic-prefix-mismatch",
    "default-mismatch",
    "required-with-default",
    "enum-default-out-of-range",
    "type-default-mismatch",
    "missing-description",
    "malformed-prop-filter",
    "unknown-prop-filter",
    "undeclared-template-var",
    "strict-with-attrs",
]


@dataclass(frozen=True)
class LintIssue:
    rule: RuleCode
    severity: Severity
    message: str
    component_path: str
    line: int | None = None
    prop_name: str | None = None
    suggestion: str | None = None  # ready-to-paste fix when one applies
    # Structured payload for the UI translation layer. Keep as a tuple of
    # (key, value) pairs so the dataclass stays frozen/hashable. The CLI
    # output uses `message` (English, log-friendly); the web UI uses these
    # via the {% lint_message %} template tag to render translated copy.
    params: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ComponentReport:
    path: str
    issues: tuple[LintIssue, ...]

    @property
    def errors(self) -> tuple[LintIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[LintIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")

    @property
    def hints(self) -> tuple[LintIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "hint")

    @property
    def is_clean(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class LintReport:
    components: tuple[ComponentReport, ...]

    @property
    def total_errors(self) -> int:
        return sum(len(c.errors) for c in self.components)

    @property
    def total_warnings(self) -> int:
        return sum(len(c.warnings) for c in self.components)

    @property
    def total_hints(self) -> int:
        return sum(len(c.hints) for c in self.components)

    @property
    def clean_components(self) -> int:
        return sum(1 for c in self.components if c.is_clean)
