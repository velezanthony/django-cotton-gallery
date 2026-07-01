"""Render a Cotton tag string through Cotton's preprocessor and Django's engine.

Cotton's `CottonCompiler.process(html_string)` converts `<c-X attrs />` into
`{% cotton X %}` template tags. The processed string is then handed to
Django's template engine via `from_string`. Component files referenced
inside the tag are still resolved by Cotton's loader from disk.

Render errors are caught and rendered inline — the gallery prefers showing
a broken preview to crashing the surrounding page. Exception messages are
HTML-escaped before interpolation: parts of the message can be attacker-
influenced (component path, prop value reflected by Django/Cotton in the
error string) and the frontend injects this output via `innerHTML`.
"""

from __future__ import annotations

import html
from functools import lru_cache

from django.http import HttpRequest
from django.template import engines
from django_cotton.compiler_regex import CottonCompiler


@lru_cache(maxsize=1)
def _compiler() -> CottonCompiler:
    return CottonCompiler()


def render(request: HttpRequest, cotton_str: str) -> str:
    try:
        processed = _compiler().process(cotton_str)
        template = engines["django"].from_string(processed)
        return template.render(context=None, request=request)
    except Exception as exc:
        return f'<p class="cg-preview-error">Render error: {html.escape(str(exc))}</p>'
