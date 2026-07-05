"""Per-prop / per-component rule loop.

The main rule loop walks parsed `@prop` annotations and the `<c-vars>`
declaration in tandem, flagging mismatches. Source-level scanners that
re-read the raw template live in `_scanners.py`.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..annotations import TRUTHY_TOKENS, escape_filter_value
from ..cvars import CVar, CVarsBlock
from ..schemas import ParsedComponent, Prop
from ._types import LintIssue, Severity


def _infer_prop_type(value: str, has_value: bool) -> str:
    """Best-effort type guess from a `<c-vars>` value, used for stub suggestions.

    Heuristic:
        bare attr (no value)             → text
        True / False / true / false      → boolean
        integer or float literal         → number
        anything else                    → text
    """
    if not has_value:
        return "text"
    if value in {"True", "False", "true", "false"}:
        return "boolean"
    try:
        float(value) if "." in value else int(value)
        return "number"
    except (ValueError, TypeError):
        return "text"


def build_prop_stub(cvar: CVar) -> str:
    """Generate a ready-to-paste `@prop` line for a `<c-vars>` attribute.

    The user pastes this above their `<c-vars>` tag and fills in the
    description. Type is inferred via `_infer_prop_type`; quoting follows
    the same rules the parser expects: strings quoted, booleans/numbers
    bare. Dynamic `:` prefix is preserved.
    """
    name = cvar.name  # keeps the `:` prefix when dynamic
    ptype = _infer_prop_type(cvar.value, cvar.has_value)
    parts = [f"{name}:{ptype}"]
    if cvar.has_value:
        if ptype in ("boolean", "number"):
            parts.append(f"default:{cvar.value}")
        else:
            parts.append(f'default:"{escape_filter_value(cvar.value)}"')
    parts.append('description:""')
    return "{# @prop " + " | ".join(parts) + " #}"


def _normalise_default(value: str | bool, ptype: str) -> str:
    """Render a `Prop.default` (parsed from @prop) as it would appear in source."""
    if ptype == "boolean":
        return "True" if value in TRUTHY_TOKENS or value is True else "False"
    return str(value)


def _cvars_value_normalised(cvar: CVar, ptype: str) -> str | None:
    """Render a `<c-vars>` attribute value to compare against an @prop default.

    Returns `None` for bare attributes (no `=`) — those mean "no explicit
    default, fall back to empty string" per Cotton's docs.
    """
    if not cvar.has_value:
        return None
    if ptype == "boolean":
        return "True" if cvar.value in {"True", "true", "1"} else "False"
    return cvar.value


def check_prop_against_cvar(
    component_path: str,
    prop: Prop,
    cvar: CVar,
) -> Iterable[LintIssue]:
    # Dynamic prefix must agree on both sides.
    if prop.name.startswith(":") != cvar.dynamic:
        yield LintIssue(
            rule="dynamic-prefix-mismatch",
            severity="error",
            message=(
                f"`{prop.clean_name}`: `:` prefix mismatch — "
                f"@prop is `{prop.name}` but <c-vars> has `{cvar.name}`."
            ),
            component_path=component_path,
            line=cvar.line,
            prop_name=prop.clean_name,
            params=(("prop", prop.clean_name), ("prop_name", prop.name), ("cvar_name", cvar.name)),
        )

    # `required-with-default` is detected separately in `scan_required_with_default`
    # because the main parser silently clears `required` whenever a default is present.

    # If @prop says enum, the default (and the c-vars value) must be one of the options.
    if prop.type == "select" and prop.options:
        if prop.has_default and prop.default not in prop.options:
            yield LintIssue(
                rule="enum-default-out-of-range",
                severity="error",
                message=(
                    f"`{prop.clean_name}`: @prop default `{prop.default!r}` is "
                    f"not in options {list(prop.options)}."
                ),
                component_path=component_path,
                line=cvar.line,
                prop_name=prop.clean_name,
                params=(
                    ("prop", prop.clean_name),
                    ("source", "prop-default"),
                    ("value", repr(prop.default)),
                    ("options", str(list(prop.options))),
                ),
            )
        if cvar.has_value and cvar.value not in prop.options and cvar.value != "":
            # Skip this when the cvar value is a placeholder — but for select
            # we expect a literal option string, so anything else is wrong.
            yield LintIssue(
                rule="enum-default-out-of-range",
                severity="error",
                message=(
                    f"`{prop.clean_name}`: <c-vars> value `{cvar.value!r}` is "
                    f"not in options {list(prop.options)}."
                ),
                component_path=component_path,
                line=cvar.line,
                prop_name=prop.clean_name,
                params=(
                    ("prop", prop.clean_name),
                    ("source", "cvars-value"),
                    ("value", repr(cvar.value)),
                    ("options", str(list(prop.options))),
                ),
            )

    # Default-value mismatch — only meaningful if @prop has a default AND
    # <c-vars> set an explicit value. Bare attrs default to "" implicitly.
    if prop.has_default:
        cvar_default = _cvars_value_normalised(cvar, prop.type)
        prop_default = _normalise_default(prop.default, prop.type)
        if cvar_default is not None and cvar_default != prop_default:
            yield LintIssue(
                rule="default-mismatch",
                severity="error",
                message=(
                    f"`{prop.clean_name}`: @prop default is `{prop_default}` "
                    f"but <c-vars> has `{cvar_default}`."
                ),
                component_path=component_path,
                line=cvar.line,
                prop_name=prop.clean_name,
                params=(
                    ("prop", prop.clean_name),
                    ("prop_default", prop_default),
                    ("cvar_default", cvar_default),
                ),
            )

    if not prop.description:
        yield LintIssue(
            rule="missing-description",
            severity="warning",
            message=f"`{prop.clean_name}`: @prop has no `| description:` filter.",
            component_path=component_path,
            line=None,
            prop_name=prop.clean_name,
            params=(("prop", prop.clean_name),),
        )


def lint_one(
    component_path: str,
    parsed: ParsedComponent,
    cvars: CVarsBlock | None,
) -> tuple[LintIssue, ...]:
    issues: list[LintIssue] = []

    # `@strict` promises a closed prop set, but `{{ attrs }}` lets arbitrary
    # attributes through — the two contradict, so the "closed" promise is a lie.
    if parsed.strict and parsed.accepts_attrs:
        issues.append(
            LintIssue(
                rule="strict-with-attrs",
                severity="error",
                message=(
                    "Component is `@strict` (closed prop set) but also renders "
                    "`{{ attrs }}`, so arbitrary attributes still pass through. "
                    "Drop `@strict` or stop spreading `{{ attrs }}`."
                ),
                component_path=component_path,
                params=(),
            )
        )

    has_props = bool(parsed.props)
    has_cvars = cvars is not None

    if has_props and not has_cvars:
        issues.append(
            LintIssue(
                rule="missing-cvars",
                severity="warning",
                message=(
                    "Component declares `@prop` annotations but no `<c-vars>` "
                    "tag — Cotton will not pass anything to the template."
                ),
                component_path=component_path,
                params=(),
            )
        )
        return tuple(issues)

    by_clean_name: dict[str, CVar] = {}
    if cvars:
        for cv in cvars.attrs:
            by_clean_name[cv.clean_name] = cv

    annotated: set[str] = set()
    for prop in parsed.props:
        annotated.add(prop.clean_name)
        cvar = by_clean_name.get(prop.clean_name)
        if cvar is None:
            issues.append(
                LintIssue(
                    rule="orphan-annotation",
                    severity="error",
                    message=(
                        f"`{prop.clean_name}`: @prop is declared but missing from "
                        "<c-vars> — the prop will never reach the template."
                    ),
                    component_path=component_path,
                    prop_name=prop.clean_name,
                    params=(("prop", prop.clean_name),),
                )
            )
            continue
        issues.extend(check_prop_against_cvar(component_path, prop, cvar))

    # Reverse direction: cvars without an @prop comment. Normally a warning,
    # but under `@strict` (closed prop set) an undocumented prop is a hard
    # contradiction — the component promised every prop is declared.
    if cvars:
        for cv in cvars.attrs:
            if cv.clean_name not in annotated:
                if parsed.strict:
                    severity: Severity = "error"
                    message = (
                        f"`{cv.clean_name}`: declared in <c-vars> but no `@prop` — "
                        "the component is `@strict`, so every prop must be documented."
                    )
                else:
                    severity = "warning"
                    message = (
                        f"`{cv.clean_name}`: declared in <c-vars> but no "
                        "`@prop` comment documents it."
                    )
                issues.append(
                    LintIssue(
                        rule="missing-annotation",
                        severity=severity,
                        message=message,
                        component_path=component_path,
                        line=cv.line,
                        prop_name=cv.clean_name,
                        suggestion=build_prop_stub(cv),
                        params=(("prop", cv.clean_name),),
                    )
                )

    return tuple(issues)
