"""Parser for the `<c-vars>` declaration tag.

Each component template is expected to declare its public props via a single
`<c-vars>` tag — Cotton's official way of saying "these are the props this
component accepts". The annotation linter cross-references this declaration
against the human-readable `@prop` comments above it.

Pure — no I/O, no Django imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Match the opening `<c-vars ... />` (or `<c-vars ...>` if non-self-closing).
# The attrs body is everything between the tag name and the closing `>`.
_CVARS_TAG = re.compile(r"<c-vars\b([^>]*?)\s*/?>", re.IGNORECASE)

# Django comments — `{# ... #}`. We blank these out (preserving offsets so
# line numbers stay accurate) before scanning for `<c-vars>` so a literal
# tag mention inside a comment doesn't shadow the real declaration.
_DJANGO_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)

# Each attribute can be:
#   name="value"   → double-quoted string
#   name='value'   → single-quoted string (Cotton accepts both; a value
#                    containing double quotes has to be wrapped this way)
#   name=value     → unquoted token (e.g. False, 0, 1.5)
#   name           → bare flag (default = "")
# The optional leading `:` marks a dynamic prop.
_ATTR = re.compile(r'(:?[A-Za-z_][\w-]*)(?:=(?:"([^"]*)"|\'([^\']*)\'|([^\s"\']+)))?')


@dataclass(frozen=True)
class CVar:
    """A single attribute declared on the `<c-vars>` tag."""

    name: str  # raw, includes leading `:` if dynamic
    clean_name: str  # without the leading `:`
    dynamic: bool  # True when the source had `:name="..."`
    has_value: bool  # False when the attribute was bare (no `=`)
    value: str  # raw value as written in source (unquoted strings, identifiers, etc.)
    line: int  # 1-based line number where the attribute appears


@dataclass(frozen=True)
class CVarsBlock:
    """The parsed `<c-vars>` tag for a component, or `None` if the tag is absent."""

    line: int  # 1-based line of the opening `<c-vars`
    attrs: tuple[CVar, ...]


def parse_cvars(source: str) -> CVarsBlock | None:
    """Locate the first `<c-vars>` tag in the source and parse its attributes.

    Returns `None` if the tag is missing — the linter can decide whether
    that's an error (component has props) or fine (no props at all).
    """
    # Blank out Django `{# ... #}` comments first — replacing with spaces
    # of the same length so all offsets / line numbers match the original.
    cleaned = _DJANGO_COMMENT.sub(lambda m: " " * len(m.group(0)), source)

    match = _CVARS_TAG.search(cleaned)
    if not match:
        return None
    tag_line = cleaned.count("\n", 0, match.start()) + 1
    attrs_body = match.group(1) or ""
    body_start = match.start(1)

    attrs = []
    for m in _ATTR.finditer(attrs_body):
        offset = body_start + m.start()
        line = cleaned.count("\n", 0, offset) + 1
        name = m.group(1)
        if m.group(2) is not None:
            value = m.group(2)
            has_value = True
        elif m.group(3) is not None:
            value = m.group(3)
            has_value = True
        elif m.group(4) is not None:
            value = m.group(4)
            has_value = True
        else:
            value = ""
            has_value = False
        attrs.append(
            CVar(
                name=name,
                clean_name=name.lstrip(":"),
                dynamic=name.startswith(":"),
                has_value=has_value,
                value=value,
                line=line,
            )
        )
    return CVarsBlock(line=tag_line, attrs=tuple(attrs))
