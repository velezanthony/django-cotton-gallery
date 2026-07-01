"""Source-level scanners that flag issues the main rule loop can't see.

The main `_lint_one` walks parsed `@prop` / `<c-vars>` data — but Cotton's
parser silently coerces some malformed input (drops `required` when a
default is present, normalises booleans). The scanners here re-read the
RAW source so we can surface those silently-fixed cases as documentation
errors.

Same module also hosts the heuristic template-var scanner — a `hint`
severity check, NOT a warning, because context-processor variables
legitimately trip it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..cvars import CVarsBlock
from ._types import LintIssue

# Raw @prop scanner used to detect cases the main parser silently fixes —
# notably `| required` co-existing with `| default:` (parser drops required)
# and bad boolean defaults (parser coerces unknown tokens to False).
_RAW_PROP = re.compile(r"\{#\s*@prop\s+(.+?)\s*#\}")
_HAS_REQUIRED = re.compile(r"\|\s*required\b")
_HAS_DEFAULT = re.compile(r"\|\s*default\s*:")
_RAW_DEFAULT = re.compile(r"\|\s*default\s*:\s*(?:\"([^\"]*)\"|(\S+))")
_RAW_HEAD = re.compile(r"^\s*(:?[\w-]+):(\w+)")

# Booleans recognised without ambiguity. The parser is more permissive
# (accepts "on", etc.) but the linter wants to flag anything that isn't
# obviously a boolean to keep documentation readable.
_VALID_BOOL_TOKENS = frozenset({"True", "False", "true", "false", "1", "0"})

# Heuristic template-var reference scan. Captures `{{ x }}`, `{{ x.y.z }}`,
# and `{{ x|filter:y }}` — we strip filters and dotted lookups to get the
# root identifier.
_VAR_REF = re.compile(r"\{\{\s*([^|}]+?)\s*(?:\|[^}]*)?\}\}")
# Same comment pattern as cvars.py — used to blank out `{# ... #}` so we
# don't pick up `{{ x }}` references that live inside a comment.
_DJANGO_COMMENT_RE = re.compile(r"\{#.*?#\}", re.DOTALL)

# Template locals we have to recognise so we don't flag legitimate uses:
#   {% for x in y %}        / {% for a, b in y %}
#   {% with x=y z=w %}
#   {% url 'name' as x %}   / {% include … as x %} / {% blocktranslate count x=y %}
_FOR_VARS = re.compile(r"\{%\s*for\s+([\w,\s]+?)\s+in\s")
_WITH_BLOCK = re.compile(r"\{%\s*with\s+([^%]+?)\s*%\}")
_AS_VAR = re.compile(r"\bas\s+(\w+)\s*%\}")
_BLOCKTRANSLATE_COUNT = re.compile(
    r"\{%\s*blocktranslate\b[^%]*?\bcount\s+(\w+)\s*=", re.IGNORECASE
)
_NAMED_SLOT = re.compile(r"\{#\s*@slot:(\w+)")

# Names that always exist in any reasonable Cotton/Django render context.
_COTTON_RESERVED = frozenset({"slot", "attrs"})
_DJANGO_RESERVED = frozenset(
    {
        "request",
        "user",
        "perms",
        "messages",
        "csrf_token",
        "LANGUAGE_CODE",
        "LANGUAGES",
        "LANGUAGE_BIDI",
        "DEBUG",
        "MEDIA_URL",
        "STATIC_URL",
        "STATIC_ROOT",
        "block",
        "forloop",
        "True",
        "False",
        "None",
    }
)


def scan_type_default_mismatch(component_path: str, source: str) -> Iterable[LintIssue]:
    """Flag `@prop` defaults that don't match the declared type.

    Boolean is checked from the raw source because the main parser silently
    coerces unknown tokens to `False` via TRUTHY_TOKENS — that obscures the
    documentation bug at runtime. Number is checked by trying to parse the
    raw token as int or float.
    """
    for match in _RAW_PROP.finditer(source):
        body = match.group(1)
        head_match = _RAW_HEAD.match(body)
        if not head_match:
            continue
        name = head_match.group(1).lstrip(":")
        ptype = head_match.group(2)
        default_match = _RAW_DEFAULT.search(body)
        if not default_match:
            continue
        raw = (
            default_match.group(1) if default_match.group(1) is not None else default_match.group(2)
        )
        line = source.count("\n", 0, match.start()) + 1

        if ptype == "boolean" and raw not in _VALID_BOOL_TOKENS:
            yield LintIssue(
                rule="type-default-mismatch",
                severity="error",
                message=(
                    f"`{name}`: type is `boolean` but default `{raw!r}` is not a "
                    "recognized boolean (use True/False/1/0)."
                ),
                component_path=component_path,
                line=line,
                prop_name=name,
                params=(("prop", name), ("expected_type", "boolean"), ("raw", repr(raw))),
            )
        elif ptype == "number":
            try:
                float(raw) if "." in raw else int(raw)
            except (ValueError, TypeError):
                yield LintIssue(
                    rule="type-default-mismatch",
                    severity="error",
                    message=(
                        f"`{name}`: type is `number` but default `{raw!r}` is not a valid number."
                    ),
                    component_path=component_path,
                    line=line,
                    prop_name=name,
                    params=(("prop", name), ("expected_type", "number"), ("raw", repr(raw))),
                )


def scan_required_with_default(component_path: str, source: str) -> Iterable[LintIssue]:
    """Detect `| required` + `| default:` on the same @prop line.

    The main parser silently drops `required` when a default is present
    (so runtime consumers get a sane Prop). The linter wants to surface
    that as a documentation error — re-scan the raw source ourselves.
    """
    for match in _RAW_PROP.finditer(source):
        body = match.group(1)
        if not (_HAS_REQUIRED.search(body) and _HAS_DEFAULT.search(body)):
            continue
        head = body.split("|", 1)[0]
        name_match = _RAW_HEAD.match(head)
        name = name_match.group(1).lstrip(":") if name_match else "?"
        line = source.count("\n", 0, match.start()) + 1
        yield LintIssue(
            rule="required-with-default",
            severity="error",
            message=(
                f"`{name}`: cannot use `| required` together with "
                "`| default:` — a required prop has no fallback."
            ),
            component_path=component_path,
            line=line,
            prop_name=name,
            params=(("prop", name),),
        )


def scan_undeclared_template_vars(
    component_path: str,
    source: str,
    cvars: CVarsBlock | None,
) -> Iterable[LintIssue]:
    """Heuristic check for `{{ x }}` references that aren't in <c-vars>.

    Marked as a HINT (not an error or warning), because the rule is
    inherently incomplete — custom context processors, included templates,
    and tag libraries can introduce names that look undeclared but are
    valid. Hints don't subtract from the Insights health score.
    """
    # Blank out `{# ... #}` comments first so we don't flag references that
    # live inside doc comments. Same length-preserving trick as cvars.py.
    cleaned = _DJANGO_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), source)

    declared = {cv.clean_name for cv in cvars.attrs} if cvars else set()
    locals_in_template: set[str] = set()

    for m in _FOR_VARS.finditer(cleaned):
        for name in (n.strip() for n in m.group(1).split(",")):
            if name:
                locals_in_template.add(name)
    for m in _WITH_BLOCK.finditer(cleaned):
        for kv in m.group(1).split():
            if "=" in kv:
                locals_in_template.add(kv.split("=", 1)[0].strip())
    for m in _AS_VAR.finditer(cleaned):
        locals_in_template.add(m.group(1))
    for m in _BLOCKTRANSLATE_COUNT.finditer(cleaned):
        locals_in_template.add(m.group(1))

    # Named slots ARE inside comments (`{# @slot:foo ... #}`) so we read
    # them from the original source, not the blanked-out version.
    named_slots = {m.group(1) for m in _NAMED_SLOT.finditer(source)}

    allowed = declared | _COTTON_RESERVED | _DJANGO_RESERVED | locals_in_template | named_slots

    seen_at_line: set[tuple[str, int]] = set()
    for m in _VAR_REF.finditer(cleaned):
        ref = m.group(1).strip()
        if not ref:
            continue
        # Strip filter args and take the root before any dotted lookup.
        ref = ref.split("|", 1)[0].strip()
        root = ref.split(".", 1)[0].strip()
        if not root:
            continue
        # Skip literal numbers and quoted strings (`{{ "x" }}`, `{{ 0 }}`).
        if not (root[0].isalpha() or root[0] == "_"):
            continue
        if root in allowed:
            continue
        line = cleaned.count("\n", 0, m.start()) + 1
        if (root, line) in seen_at_line:
            continue
        seen_at_line.add((root, line))
        yield LintIssue(
            rule="undeclared-template-var",
            severity="hint",
            message=(
                f"`{{{{ {root} }}}}` is referenced but not declared in <c-vars>. "
                "Heuristic — ignore if it comes from a custom context processor."
            ),
            component_path=component_path,
            line=line,
            prop_name=root,
            params=(("ref", root),),
        )
