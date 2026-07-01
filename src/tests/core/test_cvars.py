"""Tests for the `<c-vars>` parser used by the linter."""

from django_cotton_gallery.core.cvars import parse_cvars


class TestPresence:
    def test_returns_none_when_no_cvars(self):
        assert parse_cvars("<div>no cvars here</div>") is None

    def test_finds_self_closing_tag(self):
        block = parse_cvars('<c-vars label="x" />')
        assert block is not None
        assert block.attrs[0].clean_name == "label"

    def test_finds_non_self_closing_tag(self):
        block = parse_cvars('<c-vars label="x">something</c-vars>')
        assert block is not None
        assert block.attrs[0].clean_name == "label"

    def test_ignores_cvars_inside_django_comment(self):
        # The literal `<c-vars>` mention inside a {# ... #} comment must not
        # shadow the real declaration further down the source.
        source = '{# Mentions <c-vars> in this comment #}\n<c-vars real="yes" />'
        block = parse_cvars(source)
        assert block is not None
        assert len(block.attrs) == 1
        assert block.attrs[0].clean_name == "real"


class TestAttributes:
    def test_quoted_value(self):
        block = parse_cvars('<c-vars name="hello world" />')
        attr = block.attrs[0]
        assert attr.value == "hello world"
        assert attr.has_value is True
        assert attr.dynamic is False

    def test_unquoted_value(self):
        block = parse_cvars("<c-vars loading=False />")
        attr = block.attrs[0]
        assert attr.value == "False"
        assert attr.has_value is True

    def test_bare_attribute_has_no_value(self):
        block = parse_cvars("<c-vars title />")
        attr = block.attrs[0]
        assert attr.has_value is False
        assert attr.value == ""

    def test_dynamic_prefix_is_detected(self):
        block = parse_cvars('<c-vars :items="[]" />')
        attr = block.attrs[0]
        assert attr.dynamic is True
        assert attr.name == ":items"
        assert attr.clean_name == "items"

    def test_multiple_attrs_preserve_order(self):
        block = parse_cvars('<c-vars a="1" b="2" c="3" />')
        names = [a.clean_name for a in block.attrs]
        assert names == ["a", "b", "c"]

    def test_mix_of_quoted_unquoted_and_bare(self):
        block = parse_cvars('<c-vars title kind="primary" loading=False />')
        attrs = {a.clean_name: a for a in block.attrs}
        assert attrs["title"].has_value is False
        assert attrs["kind"].value == "primary"
        assert attrs["loading"].value == "False"


class TestLineNumbers:
    def test_block_line_is_one_indexed(self):
        source = "\n\n<c-vars x />\n"
        block = parse_cvars(source)
        assert block.line == 3

    def test_attribute_line_tracks_source_line(self):
        # Multi-line declaration — each attr should report its own line.
        source = '<c-vars\n  variant="primary"\n  size="md"\n/>\n'
        block = parse_cvars(source)
        attrs = {a.clean_name: a for a in block.attrs}
        assert attrs["variant"].line == 2
        assert attrs["size"].line == 3
