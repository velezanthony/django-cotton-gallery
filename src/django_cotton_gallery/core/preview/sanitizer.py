"""XSS prevention for user-typed pass-through HTML attributes.

Validates a free-form attribute string against an allow-list grammar and
returns a safe, well-formed string suitable for direct injection into a
component tag. Anything that doesn't match the grammar is silently dropped.

Security guarantees:
- Tag-boundary escape via raw `<` / `>` is impossible (rejected).
- Attribute-boundary escape via unbalanced quotes is impossible (the parser
  walks token by token and only emits matched-quote values).
- Event-handler attributes (`on*`) are categorically denied — gallery URLs
  are shareable and a malicious link with `onclick="..."` would execute on
  the recipient's machine.
- Ampersands inside values are HTML-escaped so the rendered tag stays
  well-formed when the user types `class="a&b"`.

Pure — no I/O, no Django imports.
"""

from __future__ import annotations

import re

_ATTR = re.compile(
    r"([A-Za-z_][\w:.-]*)"
    r"(?:\s*=\s*"
    r'(?:"([^"<>\x00]*)"|'
    r"'([^'<>\x00]*)'"
    r"))?"
)
_EVENT_HANDLER = re.compile(r"^on[a-z]", re.IGNORECASE)


def sanitize_extra_attrs(raw: str) -> str:
    """Return a safe attribute string built from the matched tokens in `raw`.

    Accepts zero or more space-separated tokens of the form:
        name              — boolean attribute (e.g. disabled, autofocus)
        name="value"      — double-quoted value, no `< > "` inside
        name='value'      — single-quoted value, no `< > '` inside

    Naming rules cover HTML standard attrs, ARIA (`aria-*`), data-*,
    Alpine.js (`x-on:click`), HTMX (`hx-target`), etc.
    """
    if not raw:
        return ""
    text = raw.strip()
    if not text:
        return ""

    out: list[str] = []
    pos = 0
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        match = _ATTR.match(text, pos)
        if not match or match.start() != pos:
            break
        name, dq_val, sq_val = match.group(1), match.group(2), match.group(3)
        pos = match.end()
        if _EVENT_HANDLER.match(name):
            continue
        if dq_val is not None:
            out.append(f'{name}="{dq_val.replace("&", "&amp;")}"')
        elif sq_val is not None:
            out.append(f"{name}='{sq_val.replace('&', '&amp;')}'")
        else:
            out.append(name)
    return " ".join(out)
