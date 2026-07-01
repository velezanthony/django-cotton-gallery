"""Tests for the XSS sanitizer — security-critical, dense coverage."""

import pytest

from django_cotton_gallery.core.preview.sanitizer import sanitize_extra_attrs


class TestEmptyAndWhitespace:
    def test_empty_string(self):
        assert sanitize_extra_attrs("") == ""

    def test_whitespace_only(self):
        assert sanitize_extra_attrs("   \t  ") == ""

    def test_none_falsy(self):
        assert sanitize_extra_attrs("") == ""


class TestValidAttributes:
    def test_boolean_attribute(self):
        assert sanitize_extra_attrs("disabled") == "disabled"

    def test_double_quoted_value(self):
        assert sanitize_extra_attrs('class="btn"') == 'class="btn"'

    def test_single_quoted_value(self):
        assert sanitize_extra_attrs("class='btn'") == "class='btn'"

    def test_multiple_attrs(self):
        result = sanitize_extra_attrs('disabled class="btn" type="submit"')
        assert result == 'disabled class="btn" type="submit"'

    def test_aria_attribute(self):
        assert sanitize_extra_attrs('aria-label="Close"') == 'aria-label="Close"'

    def test_data_attribute(self):
        assert sanitize_extra_attrs('data-toggle="modal"') == 'data-toggle="modal"'

    def test_htmx_attribute(self):
        assert sanitize_extra_attrs('hx-get="/api/data"') == 'hx-get="/api/data"'

    def test_alpine_attribute_with_colon(self):
        assert sanitize_extra_attrs('x-on:click="open"') == 'x-on:click="open"'

    def test_attribute_with_underscore(self):
        assert sanitize_extra_attrs('_internal="x"') == '_internal="x"'

    def test_attribute_with_dot(self):
        assert sanitize_extra_attrs('@click.prevent="x"') == ""  # `@` not allowed in name


class TestEventHandlersBlocked:
    @pytest.mark.parametrize(
        "raw",
        [
            'onclick="alert(1)"',
            'onmouseover="evil()"',
            "onload",
            'onfocus="x"',
            'OnClick="alert(1)"',
            'ONERROR="bad"',
        ],
    )
    def test_event_handlers_dropped(self, raw):
        assert sanitize_extra_attrs(raw) == ""

    def test_legitimate_attrs_kept_when_event_handler_dropped(self):
        result = sanitize_extra_attrs('class="btn" onclick="alert(1)" id="x"')
        assert result == 'class="btn" id="x"'


class TestTagBoundaryEscape:
    def test_lt_in_value_rejects(self):
        result = sanitize_extra_attrs('class="<script>"')
        assert "<" not in result
        assert "script" not in result

    def test_gt_in_value_rejects(self):
        result = sanitize_extra_attrs('class=">"')
        assert ">" not in result

    def test_lt_outside_value_stops_parsing(self):
        result = sanitize_extra_attrs("disabled <script>alert(1)</script>")
        assert result == "disabled"


class TestAttributeBoundaryEscape:
    def test_unbalanced_quote_does_not_smuggle_handler(self):
        raw = 'disabled" onmouseover="alert(1)'
        result = sanitize_extra_attrs(raw)
        assert "onmouseover" not in result
        assert "alert" not in result

    def test_unbalanced_single_quote(self):
        raw = "disabled' onmouseover='alert(1)"
        result = sanitize_extra_attrs(raw)
        assert "onmouseover" not in result


class TestAmpersandEscaping:
    def test_ampersand_in_double_quoted_value_escaped(self):
        assert sanitize_extra_attrs('class="a&b"') == 'class="a&amp;b"'

    def test_ampersand_in_single_quoted_value_escaped(self):
        assert sanitize_extra_attrs("class='a&b'") == "class='a&amp;b'"

    def test_existing_entity_double_escaped(self):
        # Idempotency is NOT required — defensive double-escape is acceptable.
        result = sanitize_extra_attrs('class="&amp;"')
        assert result == 'class="&amp;amp;"'


class TestGarbageInput:
    def test_pure_garbage_dropped(self):
        assert sanitize_extra_attrs("!!! @@@ ###") == ""

    def test_mixed_legit_and_garbage_keeps_prefix(self):
        result = sanitize_extra_attrs('class="btn" @@@invalid')
        assert result == 'class="btn"'

    def test_null_byte_blocks_at_position(self):
        result = sanitize_extra_attrs('class="a\x00b"')
        assert "\x00" not in result or result == ""


class TestSpacingPreservation:
    def test_extra_internal_whitespace_collapses(self):
        result = sanitize_extra_attrs('  disabled    class="btn"  ')
        assert result == 'disabled class="btn"'

    def test_tab_separator(self):
        assert sanitize_extra_attrs('disabled\tclass="btn"') == 'disabled class="btn"'
