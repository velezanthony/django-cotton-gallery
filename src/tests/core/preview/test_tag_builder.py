"""Tests for Cotton tag composition."""

from django_cotton_gallery.core.preview.tag_builder import build_default_tag, build_tag
from django_cotton_gallery.core.schemas import ParsedComponent, Prop, Slot


def _parsed(*, props=(), slots=(), trigger="", accepts_attrs=False) -> ParsedComponent:
    return ParsedComponent(props=props, slots=slots, trigger=trigger, accepts_attrs=accepts_attrs)


class TestBuildTag:
    def test_minimal_self_closing(self):
        result = build_tag("atoms.button", _parsed(), {})
        assert result == "<c-atoms.button  />"

    def test_text_prop_default(self):
        parsed = _parsed(
            props=(
                Prop(
                    name="label", clean_name="label", type="text", default="Click", has_default=True
                ),
            )
        )
        assert build_tag("atoms.button", parsed, {}) == '<c-atoms.button label="Click" />'

    def test_text_prop_override(self):
        parsed = _parsed(
            props=(
                Prop(
                    name="label", clean_name="label", type="text", default="Click", has_default=True
                ),
            )
        )
        assert (
            build_tag("atoms.button", parsed, {"label": "Save"})
            == '<c-atoms.button label="Save" />'
        )

    def test_boolean_prop_truthy(self):
        parsed = _parsed(
            props=(
                Prop(
                    name="loading",
                    clean_name="loading",
                    type="boolean",
                    default=False,
                    has_default=True,
                ),
            )
        )
        assert build_tag("atoms.btn", parsed, {"loading": "True"}) == "<c-atoms.btn loading />"

    def test_boolean_prop_falsy_omitted(self):
        parsed = _parsed(
            props=(
                Prop(
                    name="loading",
                    clean_name="loading",
                    type="boolean",
                    default=False,
                    has_default=True,
                ),
            )
        )
        assert build_tag("atoms.btn", parsed, {}) == "<c-atoms.btn  />"

    def test_dynamic_prop_keeps_colon_in_output(self):
        parsed = _parsed(
            props=(
                Prop(
                    name=":count", clean_name="count", type="number", default="5", has_default=True
                ),
            )
        )
        result = build_tag("atoms.badge", parsed, {})
        assert ':count="5"' in result

    def test_default_slot_with_content(self):
        parsed = _parsed(slots=(Slot(name=None, content="Click me"),))
        assert build_tag("atoms.btn", parsed, {}) == "<c-atoms.btn >Click me</c-atoms.btn>"

    def test_default_slot_overridden(self):
        parsed = _parsed(slots=(Slot(name=None, content="Click me"),))
        assert (
            build_tag("atoms.btn", parsed, {"_slot": "Save"}) == "<c-atoms.btn >Save</c-atoms.btn>"
        )

    def test_named_slot(self):
        parsed = _parsed(slots=(Slot(name="actions", content="<btn />"),))
        result = build_tag("molecules.card", parsed, {})
        assert '<c-slot name="actions"><btn /></c-slot>' in result

    def test_named_slot_overridden(self):
        parsed = _parsed(slots=(Slot(name="actions", content="<btn />"),))
        result = build_tag("molecules.card", parsed, {"_slot__actions": "<custom />"})
        assert '<c-slot name="actions"><custom /></c-slot>' in result

    def test_extra_attrs_when_accepts(self):
        parsed = _parsed(accepts_attrs=True)
        result = build_tag("atoms.input", parsed, {"__extra_attrs": 'placeholder="Email"'})
        assert 'placeholder="Email"' in result

    def test_extra_attrs_ignored_when_not_accepts(self):
        parsed = _parsed(accepts_attrs=False)
        result = build_tag("atoms.input", parsed, {"__extra_attrs": 'placeholder="Email"'})
        assert "placeholder" not in result

    def test_trigger_inside_tag_body(self):
        parsed = _parsed(trigger="<button>Open</button>", slots=(Slot(name=None, content=""),))
        # trigger is treated as inner content
        result = build_tag("molecules.modal", parsed, {})
        assert "<button>Open</button>" in result


class TestBuildDefaultTag:
    def test_only_uses_declared_defaults(self):
        parsed = _parsed(
            props=(
                Prop(
                    name="label", clean_name="label", type="text", default="Click", has_default=True
                ),
            )
        )
        # params would normally override, but build_default_tag ignores them
        assert build_default_tag("atoms.btn", parsed) == '<c-atoms.btn label="Click" />'

    def test_boolean_true_default_emitted(self):
        parsed = _parsed(
            props=(
                Prop(
                    name="loading",
                    clean_name="loading",
                    type="boolean",
                    default=True,
                    has_default=True,
                ),
            )
        )
        assert build_default_tag("atoms.btn", parsed) == "<c-atoms.btn loading />"

    def test_boolean_false_default_omitted(self):
        parsed = _parsed(
            props=(
                Prop(
                    name="loading",
                    clean_name="loading",
                    type="boolean",
                    default=False,
                    has_default=True,
                ),
            )
        )
        assert build_default_tag("atoms.btn", parsed) == "<c-atoms.btn  />"

    def test_named_slot_default_content_included(self):
        parsed = _parsed(slots=(Slot(name="actions", content="<btn />"),))
        result = build_default_tag("molecules.card", parsed)
        assert '<c-slot name="actions"><btn /></c-slot>' in result

    def test_named_slot_empty_omitted(self):
        parsed = _parsed(slots=(Slot(name="actions", content=""),))
        result = build_default_tag("molecules.card", parsed)
        assert "c-slot" not in result


class TestPropValueEscaping:
    """Regression tests — prop values come from request.GET and MUST be HTML-escaped.

    Without escaping, a value like `primary" onclick="alert(1)` breaks out of the
    attribute and Cotton then parses the runaway text as a SECOND attribute
    (`onclick="alert(1)"`), forwarding it to `{{ attrs }}` and into the rendered
    HTML where the frontend's `innerHTML` makes the handler live. The fix lives
    in `tag_builder._escape_attr`.
    """

    def test_double_quote_in_value_does_not_form_second_attribute(self):
        parsed = _parsed(
            props=(
                Prop(name="label", clean_name="label", type="text", default="", has_default=True),
            )
        )
        result = build_tag("atoms.btn", parsed, {"label": 'a" onclick="alert(1)'})
        # The closing quote must be escaped; without that, Cotton sees a second attribute.
        assert '" onclick=' not in result
        assert "&quot;" in result

    def test_single_quote_in_value_is_preserved(self):
        # Single quotes are NOT escaped: the attr boundary is `"`, so a
        # single quote can't break out — and Cotton evaluates dynamic-prop
        # values as Python code, where `'` is a valid string-literal char.
        # Escaping it would break `:steps="['a', 'b']"` etc.
        parsed = _parsed(
            props=(
                Prop(name="label", clean_name="label", type="text", default="", has_default=True),
            )
        )
        result = build_tag("atoms.btn", parsed, {"label": "a' b"})
        assert "a' b" in result
        assert "&#x27;" not in result

    def test_angle_brackets_in_value_are_escaped(self):
        parsed = _parsed(
            props=(
                Prop(name="label", clean_name="label", type="text", default="", has_default=True),
            )
        )
        result = build_tag("atoms.btn", parsed, {"label": "<script>alert(1)</script>"})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_ampersand_in_value_is_escaped(self):
        parsed = _parsed(
            props=(
                Prop(name="label", clean_name="label", type="text", default="", has_default=True),
            )
        )
        result = build_tag("atoms.btn", parsed, {"label": "Tom & Jerry"})
        assert "Tom &amp; Jerry" in result

    def test_default_path_also_escapes(self):
        """Defaults come from component source — usually trusted — but the escape path is the same."""
        parsed = _parsed(
            props=(
                Prop(
                    name="label", clean_name="label", type="text", default='a"b', has_default=True
                ),
            )
        )
        assert build_default_tag("atoms.btn", parsed) == '<c-atoms.btn label="a&quot;b" />'
