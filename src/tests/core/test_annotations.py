"""Tests for the annotation parser."""

from django_cotton_gallery.core.annotations import AnnotationParser


class TestDescription:
    def test_extract_simple(self):
        source = "{# @description A button component #}"
        assert AnnotationParser.extract_description(source) == "A button component"

    def test_extract_missing_returns_empty(self):
        assert AnnotationParser.extract_description("<div></div>") == ""

    def test_extract_strips_whitespace(self):
        source = "{# @description    Padded description    #}"
        assert AnnotationParser.extract_description(source) == "Padded description"

    def test_full_parse_includes_description(self):
        parsed = AnnotationParser().parse("{# @description Tooltip #}")
        assert parsed.description == "Tooltip"


class TestPropBasic:
    def test_text_prop(self):
        source = '{# @prop label:text | default:"Click" #}'
        parsed = AnnotationParser().parse(source)
        assert len(parsed.props) == 1
        prop = parsed.props[0]
        assert prop.name == "label"
        assert prop.clean_name == "label"
        assert prop.type == "text"
        assert prop.default == "Click"
        assert prop.has_default is True

    def test_dynamic_prop_keeps_colon_in_name(self):
        source = "{# @prop :count:number | default:5 #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.name == ":count"
        assert prop.clean_name == "count"

    def test_invalid_head_is_skipped(self):
        source = "{# @prop garbage-no-type #}"
        parsed = AnnotationParser().parse(source)
        assert parsed.props == ()

    def test_multiple_props_in_order(self):
        source = "{# @prop a:text #}\n{# @prop b:text #}\n{# @prop c:text #}\n"
        names = [p.name for p in AnnotationParser().parse(source).props]
        assert names == ["a", "b", "c"]


class TestPropFilters:
    def test_required(self):
        prop = AnnotationParser().parse("{# @prop x:text | required #}").props[0]
        assert prop.required is True
        assert prop.has_default is False

    def test_default_wins_over_required(self):
        source = '{# @prop x:text | default:"hi" | required #}'
        prop = AnnotationParser().parse(source).props[0]
        assert prop.required is False
        assert prop.has_default is True
        assert prop.default == "hi"

    def test_description(self):
        source = '{# @prop x:text | description:"the x value" #}'
        prop = AnnotationParser().parse(source).props[0]
        assert prop.description == "the x value"

    def test_deprecated(self):
        source = '{# @prop old:text | deprecated:"use new" #}'
        prop = AnnotationParser().parse(source).props[0]
        assert prop.deprecated == "use new"

    def test_hidden(self):
        prop = AnnotationParser().parse("{# @prop x:text | hidden #}").props[0]
        assert prop.hidden is True

    def test_example(self):
        source = '{# @prop x:text | example:"bg-brand" #}'
        prop = AnnotationParser().parse(source).props[0]
        assert prop.example == "bg-brand"


class TestPropTypes:
    def test_select_with_options(self):
        source = (
            "{# @prop variant:select['primary', 'secondary', 'danger'] | default:\"primary\" #}"
        )
        prop = AnnotationParser().parse(source).props[0]
        assert prop.type == "select"
        assert prop.options == ("primary", "secondary", "danger")
        assert prop.default == "primary"

    def test_select_without_options(self):
        source = "{# @prop variant:select #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.options == ()

    def test_number(self):
        source = "{# @prop count:number | default:5 #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.type == "number"
        assert prop.default == "5"

    def test_boolean_default_true(self):
        source = "{# @prop loading:boolean | default:True #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.type == "boolean"
        assert prop.default is True

    def test_boolean_default_false(self):
        source = "{# @prop loading:boolean | default:False #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default is False

    def test_boolean_default_on_is_true(self):
        source = "{# @prop loading:boolean | default:on #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default is True

    def test_boolean_default_1_is_true(self):
        source = "{# @prop loading:boolean | default:1 #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default is True

    def test_boolean_no_default_keeps_empty_string(self):
        source = "{# @prop loading:boolean #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default == ""
        assert prop.has_default is False


class TestSlots:
    def test_default_slot_no_name(self):
        source = "{# @slot Default content #}"
        slot = AnnotationParser().parse(source).slots[0]
        assert slot.name is None
        assert slot.content == "Default content"

    def test_named_slot(self):
        source = "{# @slot:actions <button>Save</button> #}"
        slot = AnnotationParser().parse(source).slots[0]
        assert slot.name == "actions"
        assert slot.content == "<button>Save</button>"

    def test_slot_with_description_after_em_dash(self):
        source = "{# @slot Click me — Button label #}"
        slot = AnnotationParser().parse(source).slots[0]
        assert slot.content == "Click me"
        assert slot.description == "Button label"

    def test_slot_starting_with_em_dash_is_description_only(self):
        source = "{# @slot:breadcrumb — No default content #}"
        slot = AnnotationParser().parse(source).slots[0]
        assert slot.name == "breadcrumb"
        assert slot.content == ""
        assert slot.description == "No default content"

    def test_multiple_slots_preserved(self):
        source = "{# @slot Default — main #}\n{# @slot:actions <btn /> — buttons #}\n"
        slots = AnnotationParser().parse(source).slots
        assert len(slots) == 2
        assert slots[0].name is None
        assert slots[1].name == "actions"


class TestTrigger:
    def test_extracts_content(self):
        source = "{# @trigger <button>Open</button> — opens drawer #}"
        parsed = AnnotationParser().parse(source)
        assert parsed.trigger == "<button>Open</button>"

    def test_missing_returns_empty(self):
        assert AnnotationParser().parse("<div></div>").trigger == ""


class TestAcceptsAttrs:
    def test_double_brace_attrs(self):
        parsed = AnnotationParser().parse("<div {{ attrs }}></div>")
        assert parsed.accepts_attrs is True

    def test_attrs_with_filter(self):
        parsed = AnnotationParser().parse("<div {{ attrs|safe }}></div>")
        assert parsed.accepts_attrs is True

    def test_passthrough_attrs(self):
        parsed = AnnotationParser().parse('<c-child :attrs="attrs" />')
        assert parsed.accepts_attrs is True

    def test_no_attrs(self):
        parsed = AnnotationParser().parse("<div class='x'></div>")
        assert parsed.accepts_attrs is False


class TestStrict:
    def test_strict_flag_present(self):
        parsed = AnnotationParser().parse("{# @strict #}\n<button>{{ slot }}</button>")
        assert parsed.strict is True

    def test_strict_absent_defaults_false(self):
        parsed = AnnotationParser().parse("{# @description X #}")
        assert parsed.strict is False

    def test_strict_tolerates_whitespace(self):
        assert AnnotationParser().parse("{#   @strict   #}").strict is True

    def test_strict_requires_exact_marker(self):
        # Trailing content or a longer word must NOT count as @strict.
        assert AnnotationParser().parse("{# @strictly #}").strict is False
        assert AnnotationParser().parse("{# @strict now #}").strict is False


class TestEmptySource:
    def test_empty_string(self):
        parsed = AnnotationParser().parse("")
        assert parsed.props == ()
        assert parsed.slots == ()
        assert parsed.trigger == ""
        assert parsed.description == ""
        assert parsed.accepts_attrs is False

    def test_html_without_annotations(self):
        parsed = AnnotationParser().parse("<button>Click</button>")
        assert parsed.props == ()
        assert parsed.slots == ()


class TestRealComponent:
    def test_full_button_component(self):
        source = """
        {# @description Primary action button #}
        {# @prop variant:select['primary', 'secondary'] | default:"primary" | description:"Style" #}
        {# @prop loading:boolean | default:False | description:"Show spinner" #}
        {# @slot Click me — Button label #}
        <c-vars variant="primary" loading=False />
        <button class="btn btn-{{ variant }}" {{ attrs }}>{{ slot }}</button>
        """
        parsed = AnnotationParser().parse(source)
        assert parsed.description == "Primary action button"
        assert len(parsed.props) == 2
        assert parsed.props[0].name == "variant"
        assert parsed.props[0].options == ("primary", "secondary")
        assert parsed.props[1].name == "loading"
        assert parsed.props[1].default is False
        assert len(parsed.slots) == 1
        assert parsed.slots[0].content == "Click me"
        assert parsed.slots[0].description == "Button label"
        assert parsed.accepts_attrs is True


class TestDelimiterCollisions:
    """Values that contain the DSL's own delimiters (`|`, `"`, `'`).

    Pipes inside a quoted value or inside select[...] are content, not
    separators. Quotes inside quoted values / select options are escaped
    with a backslash (the same convention the builder emits).
    """

    def test_pipe_inside_quoted_description(self):
        source = '{# @prop size:text | default:"md" | description:"Sizes: sm | md | lg" #}'
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default == "md"
        assert prop.description == "Sizes: sm | md | lg"

    def test_pipe_inside_quoted_default(self):
        source = '{# @prop sep:text | default:"a | b" | description:"Separator" #}'
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default == "a | b"
        assert prop.description == "Separator"

    def test_escaped_double_quote_in_default(self):
        source = (
            '{# @prop greeting:text | default:"Say \\"hello\\" now" | description:"Greeting" #}'
        )
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default == 'Say "hello" now'
        assert prop.has_default is True
        assert prop.description == "Greeting"

    def test_escaped_double_quote_in_description(self):
        source = '{# @prop x:text | description:"Shows a \\"hint\\" text" #}'
        prop = AnnotationParser().parse(source).props[0]
        assert prop.description == 'Shows a "hint" text'

    def test_escaped_backslash_in_default(self):
        source = '{# @prop path:text | default:"C:\\\\temp" | description:"Path" #}'
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default == "C:\\temp"

    def test_escaped_single_quote_in_select_option(self):
        source = "{# @prop mood:select['it\\'s ok', 'bad'] | description:\"Mood\" #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.options == ("it's ok", "bad")

    def test_pipe_inside_select_options(self):
        source = "{# @prop sep:select['a|b', 'c'] | description:\"Separator\" #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.options == ("a|b", "c")
        assert prop.description == "Separator"

    def test_plain_annotations_are_unchanged(self):
        # Regression guard: the escape machinery must not alter how
        # ordinary escape-free annotations parse.
        source = "{# @prop variant:select['primary', 'secondary'] | default:\"primary\" | description:\"Style\" #}"
        prop = AnnotationParser().parse(source).props[0]
        assert prop.default == "primary"
        assert prop.description == "Style"
        assert prop.options == ("primary", "secondary")
