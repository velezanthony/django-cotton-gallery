"""Compose Cotton tag strings from parsed components and request params.

Pure — no Django imports. Receives a `Mapping[str, str]` (Django's
QueryDict is compatible) so the same builder is testable without a request.

Security note — prop values originate in `request.GET` and are interpolated
directly into HTML attributes. They MUST be HTML-escaped (including quotes)
before insertion or an attacker can break out of the value with `"` and inject
event handlers like `onclick=`. The named-prop path used to skip this; the
extra-attrs path always went through `sanitize_extra_attrs`. Both paths now
emit safe values.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..annotations import TRUTHY_TOKENS
from ..schemas import ParsedComponent, Prop, Slot
from .sanitizer import sanitize_extra_attrs

DEFAULT_SLOT_PARAM = "_slot"
NAMED_SLOT_PARAM_PREFIX = "_slot__"
EXTRA_ATTRS_PARAM = "__extra_attrs"


def build_tag(tag_path: str, parsed: ParsedComponent, params: Mapping[str, str]) -> str:
    """Build a Cotton tag string with values overridden by `params`."""
    attrs = _resolve_attrs(parsed.props, params)
    if parsed.accepts_attrs:
        extra = sanitize_extra_attrs(params.get(EXTRA_ATTRS_PARAM, ""))
        if extra:
            attrs.append(extra)
    default_content, named_fragments = _resolve_slots(parsed.slots, params)
    return _compose(tag_path, parsed.trigger, attrs, default_content, named_fragments)


def build_default_tag(tag_path: str, parsed: ParsedComponent) -> str:
    """Build a Cotton tag using only declared defaults — no request overrides."""
    attrs: list[str] = []
    for prop in parsed.props:
        value = prop.default
        if prop.type == "boolean":
            if value is True:
                attrs.append(prop.name)
        elif value not in (None, ""):
            attrs.append(_quote_attr(prop.name, value))

    default_content = ""
    named_fragments: list[str] = []
    for slot in parsed.slots:
        if slot.name is None:
            default_content = slot.content
        elif slot.content:
            named_fragments.append(f'<c-slot name="{slot.name}">{slot.content}</c-slot>')

    return _compose(tag_path, parsed.trigger, attrs, default_content, named_fragments)


def _compose(
    tag_path: str,
    trigger: str,
    attrs: list[str],
    default_content: str,
    named_fragments: list[str],
) -> str:
    inner = f"{trigger}{''.join(named_fragments)}{default_content}"
    tag = f"c-{tag_path}"
    attr_str = " ".join(attrs)
    if inner:
        return f"<{tag} {attr_str}>{inner}</{tag}>"
    return f"<{tag} {attr_str} />"


def _resolve_attrs(props: tuple[Prop, ...], params: Mapping[str, str]) -> list[str]:
    attrs: list[str] = []
    for prop in props:
        raw = params.get(prop.clean_name)
        value = prop.default if raw is None else raw

        if prop.type == "boolean":
            if value in TRUTHY_TOKENS:
                attrs.append(prop.name)
            elif prop.default is True:
                # Omitting the attr would let the component's default-True win —
                # emit an explicit False so the toggle can actually switch off.
                attrs.append(f':{prop.name}="False"')
        elif value not in (None, ""):
            attrs.append(_quote_attr(prop.name, value))
    return attrs


def _resolve_slots(slots: tuple[Slot, ...], params: Mapping[str, str]) -> tuple[str, list[str]]:
    default_content = ""
    named_fragments: list[str] = []
    for slot in slots:
        if slot.name is None:
            raw = params.get(DEFAULT_SLOT_PARAM)
            default_content = raw if raw is not None else slot.content
        else:
            raw = params.get(f"{NAMED_SLOT_PARAM_PREFIX}{slot.name}")
            content = raw if raw is not None else slot.content
            if content:
                named_fragments.append(f'<c-slot name="{slot.name}">{content}</c-slot>')
    return default_content, named_fragments


def _quote_attr(name: str, value: object) -> str:
    """Render `name=value` with a quote style the value can't break out of.

    Cotton doesn't decode entities in attr values, so `&quot;` would reach
    the runtime prop literally. Values with `"` but no `'` get single quotes
    (breakout needs the delimiter, guaranteed absent); everything else keeps
    the classic double-quote + `&quot;` path.
    """
    s = str(value)
    if '"' in s and "'" not in s:
        escaped = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"{name}='{escaped}'"
    return f'{name}="{_escape_attr(s)}"'


def _escape_attr(value: object) -> str:
    """Escape a prop value for safe insertion inside a double-quoted HTML attribute.

    Escapes `<`, `>`, `&`, and `"`. We deliberately do NOT escape `'`:

    - The attribute boundary is `"` (double-quoted branch of `_quote_attr`)
      so a single quote can't break out of the attribute.
    - Cotton evaluates dynamic-prop values (`:foo="..."`) as Python code,
      where `'` is the string-literal delimiter. Escaping it to `&#x27;`
      breaks expressions like `:steps="['a', 'b']"` — Cotton ends up with
      the literal entity, fails to parse it, and silently degrades.

    The XSS vector this guards against is `value=foo" onclick=...` — the
    `"` is what would close the attribute. Escaping that is enough.
    """
    s = str(value)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
