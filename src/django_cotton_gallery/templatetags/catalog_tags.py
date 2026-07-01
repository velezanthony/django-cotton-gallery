"""Template tags and filters used by the gallery templates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from django import template
from django.template import TemplateDoesNotExist
from django.template.base import Parser, Token
from django.template.loader import get_template
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext_lazy as _

from ..core.linter import RuleCode

register = template.Library()


# Translatable templates per lint rule. The KEY is `issue.rule` (kept in
# English as the stable identifier — same value goes into `data-cg-rule`
# attributes used for filter-matching, into `cotton_lint` CLI output, and
# into any docs/CI consumers). The VALUE is either:
#   • a single gettext string (rule has only one sentence shape), or
#   • a `(discriminant_param_key, {variant_value: gettext_string})` tuple
#     when the natural sentence shape changes per context — the tag picks
#     the variant by reading `params[discriminant_param_key]`.
# Placeholders (`%(name)s`) match the keys each rule's `params` populates.
# Keyed by `RuleCode` so mypy flags a typo'd or unknown rule key here.
_LINT_MESSAGES: dict[RuleCode, Any] = {
    "dynamic-prefix-mismatch": _(
        "`%(prop)s`: `:` prefix mismatch — @prop is `%(prop_name)s` but <c-vars> has `%(cvar_name)s`."
    ),
    "default-mismatch": _(
        "`%(prop)s`: @prop default is `%(prop_default)s` but <c-vars> has `%(cvar_default)s`."
    ),
    "missing-description": _("`%(prop)s`: @prop has no `| description:` filter."),
    "missing-cvars": _(
        "Component declares `@prop` annotations but no `<c-vars>` tag — Cotton will not pass anything to the template."
    ),
    "orphan-annotation": _(
        "`%(prop)s`: @prop is declared but missing from <c-vars> — the prop will never reach the template."
    ),
    "missing-annotation": _(
        "`%(prop)s`: declared in <c-vars> but no `@prop` comment documents it."
    ),
    "required-with-default": _(
        "`%(prop)s`: cannot use `| required` together with `| default:` — a required prop has no fallback."
    ),
    "undeclared-template-var": _(
        "`{{ %(ref)s }}` is referenced but not declared in <c-vars>. Heuristic — ignore if it comes from a custom context processor."
    ),
    "enum-default-out-of-range": (
        "source",
        {
            "prop-default": _(
                "`%(prop)s`: @prop default `%(value)s` is not in options %(options)s."
            ),
            "cvars-value": _(
                "`%(prop)s`: <c-vars> value `%(value)s` is not in options %(options)s."
            ),
        },
    ),
    "type-default-mismatch": (
        "expected_type",
        {
            "boolean": _(
                "`%(prop)s`: type is `boolean` but default `%(raw)s` is not a recognized boolean (use True/False/1/0)."
            ),
            "number": _(
                "`%(prop)s`: type is `number` but default `%(raw)s` is not a valid number."
            ),
        },
    ),
}


@register.simple_tag
def lint_message(issue: Any) -> str:
    """Render a translated message for a LintIssue.

    Looks up the translation template by `issue.rule`. If the registry
    entry is a `(discriminant, variants)` tuple, the discriminant key is
    read from `params` to pick the right sentence shape — that lets a
    single `rule` code (the public/stable identifier) carry multiple
    natural-language phrasings without inventing per-locale rule codes.

    Falls back to `issue.message` (English, log-style) when the rule has
    no registered template, when the discriminant is missing from params,
    or when interpolation fails. The CLI (`cotton_lint`) only ever reads
    `issue.message` so its output stays English by design.
    """
    rule = getattr(issue, "rule", None)
    # Runtime str → RuleCode for the lookup; an unknown code just misses and
    # falls through to the English message below, so the cast is safe.
    entry = _LINT_MESSAGES.get(cast(RuleCode, rule)) if isinstance(rule, str) else None
    if entry is None:
        return getattr(issue, "message", "")
    params = dict(getattr(issue, "params", ()) or ())
    if isinstance(entry, tuple):
        discriminant_key, variants = entry
        template_text = variants.get(params.get(discriminant_key))
        if template_text is None:
            return getattr(issue, "message", "")
    else:
        template_text = entry
    try:
        # str() forces the gettext_lazy proxy to resolve against the
        # request's active language (instead of whatever was active at
        # module import). The % interpolation happens after.
        return str(template_text) % params
    except (KeyError, ValueError):
        return getattr(issue, "message", "")


@register.simple_tag(takes_context=True)
def maybe_include(context: template.Context, template_name: str) -> str:
    """Render a template if it exists, otherwise return an empty string.

    Replaces Django's `{% include "..." ignore missing %}`, which was removed
    in Django 6. Used to render consumer-supplied partials (e.g. `_extra_head.html`).
    """
    try:
        return get_template(template_name).render(context.flatten())  # type: ignore[arg-type]
    except TemplateDoesNotExist:
        return ""


@register.tag
def codeblock(parser: Parser, token: Token) -> _CodeBlockNode:
    """Block tag that escapes its rendered content as HTML entities.

    Lets us drop raw `<button>` / `<c-vars>` snippets inside `<pre><code>`
    without the browser parsing them as real elements. Pair with `{% verbatim %}`
    inside to preserve `{{ }}` and `{% %}`.
    """
    nodelist = parser.parse(("endcodeblock",))
    parser.delete_first_token()
    return _CodeBlockNode(nodelist)


class _CodeBlockNode(template.Node):
    def __init__(self, nodelist: template.NodeList) -> None:
        self.nodelist = nodelist

    def render(self, context: template.Context) -> SafeString:
        return mark_safe(escape(self.nodelist.render(context)))


@register.filter
def component_count(subcategories: dict[str, list[Any]]) -> int:
    return sum(len(comps) for comps in subcategories.values())


@register.filter
def total_components(categories: dict[str, dict[str, list[Any]]]) -> int:
    return sum(component_count(subs) for subs in categories.values())


def _js_array(names: Iterable[str]) -> SafeString:
    inner = ",".join("'" + n + "'" for n in names)
    return mark_safe("[" + inner + "]")


@register.filter
def js_names_from_category(subcategories: dict[str, list[Any]]) -> SafeString:
    names = [c.name for sub in subcategories.values() for c in sub]
    return _js_array(names)


@register.filter
def js_names(components: Iterable[Any]) -> SafeString:
    return _js_array([c.name for c in components])


@register.filter
def lint_counts(summary: dict, path: str) -> tuple[int, int, int] | None:
    """Sidebar helper — returns `(errors, warnings, hints)` for a component
    path, or `None` if the component is fully clean. Used by per-link badges."""
    if not summary:
        return None
    return summary.get(path)


@register.simple_tag
def gallery_languages() -> tuple[tuple[str, str], ...]:
    """Locales the package ships translations for.

    Exposed as a template tag (not a context variable) so the language
    switcher in base.html works even when the consumer has not added
    `gallery_assets` to their TEMPLATES context_processors. Single
    source of truth — keep in sync with
    `django_cotton_gallery.context_processors.PACKAGE_LANGUAGES`.
    """
    from ..context_processors import PACKAGE_LANGUAGES

    return PACKAGE_LANGUAGES
