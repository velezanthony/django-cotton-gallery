"""Property-based tests for the XSS sanitizer.

Where `test_sanitizer.py` covers known attack vectors with hand-written
inputs, this file fuzzes with `hypothesis`. The goal: assert that for
ANY string input the sanitizer's output upholds these invariants:

    1. The output is a `str` (never None, never bytes, never raises).
    2. The output never contains a stray `<` or `>` (those would let an
       attacker close the host tag and inject sibling elements).
    3. The output never contains a null byte (control character that some
       browsers treat inconsistently and that some legacy parsers stop on).
    4. The output never contains an `on<event>=` pattern (event handler
       injection, the highest-impact XSS class).
    5. When wrapped into a `<button {output}>x</button>`, the result still
       parses as exactly one element with one body — no smuggled siblings.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from hypothesis import given, settings
from hypothesis import strategies as st

from django_cotton_gallery.core.preview.sanitizer import sanitize_extra_attrs

# Very wide alphabet: ASCII + common non-ASCII + control characters.
# Hypothesis will minimize counterexamples, so even an exotic byte that
# breaks the sanitizer comes back as a small repro.
FUZZ_INPUTS = st.text(
    alphabet=st.characters(codec="utf-8"),
    max_size=200,
)

EVENT_HANDLER_PATTERN = re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE)


class _ElementCounter(HTMLParser):
    """Counts top-level elements seen — used to detect tag smuggling."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.start_tags: list[str] = []
        self.end_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        self.end_tags.append(tag)


@given(FUZZ_INPUTS)
@settings(max_examples=500, deadline=None)
def test_output_is_always_a_string(raw: str) -> None:
    result = sanitize_extra_attrs(raw)
    assert isinstance(result, str)


@given(FUZZ_INPUTS)
@settings(max_examples=500, deadline=None)
def test_no_null_byte_in_output(raw: str) -> None:
    result = sanitize_extra_attrs(raw)
    assert "\x00" not in result


@given(FUZZ_INPUTS)
@settings(max_examples=500, deadline=None)
def test_no_lt_or_gt_in_output(raw: str) -> None:
    result = sanitize_extra_attrs(raw)
    assert "<" not in result, f"Output contains '<' for input {raw!r}: {result!r}"
    assert ">" not in result, f"Output contains '>' for input {raw!r}: {result!r}"


@given(FUZZ_INPUTS)
@settings(max_examples=500, deadline=None)
def test_no_event_handler_attribute(raw: str) -> None:
    result = sanitize_extra_attrs(raw)
    assert not EVENT_HANDLER_PATTERN.search(result), (
        f"Event handler leaked through for input {raw!r}: {result!r}"
    )


@given(FUZZ_INPUTS)
@settings(max_examples=500, deadline=None)
def test_no_tag_smuggling_when_wrapped(raw: str) -> None:
    """Wrap the sanitized output into a host tag and assert exactly one
    element with one body comes back. Anything more is a smuggled sibling."""
    sanitized = sanitize_extra_attrs(raw)
    html = f"<button {sanitized}>x</button>"
    parser = _ElementCounter()
    parser.feed(html)
    assert parser.start_tags == ["button"], (
        f"Tag smuggling for input {raw!r}: parsed start tags {parser.start_tags}"
    )
    assert parser.end_tags == ["button"], (
        f"Tag smuggling for input {raw!r}: parsed end tags {parser.end_tags}"
    )


@given(FUZZ_INPUTS)
@settings(max_examples=300, deadline=None)
def test_idempotent_on_already_safe_output(raw: str) -> None:
    """Sanitizing twice should produce the same result as sanitizing once.

    Idempotency ensures the function reaches a stable fixed point and there
    are no infinite escape-cycles (each pass adds more `&amp;` indefinitely).
    """
    once = sanitize_extra_attrs(raw)
    twice = sanitize_extra_attrs(once)
    assert once == twice, (
        f"Sanitizer is not idempotent for input {raw!r}: once={once!r}, twice={twice!r}"
    )
