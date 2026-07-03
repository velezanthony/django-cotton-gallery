"""Tests for the annotation linter.

Each rule has its own test class. Helpers below take a synthetic source
string, run the linter, and return the issues so the tests can assert
shape directly without going through the catalog/Django plumbing.
"""

from django_cotton_gallery.core.linter import lint_component


def _rules(source: str) -> list[str]:
    """Return only the rule names from the linter — used when shape matters."""
    return [issue.rule for issue in lint_component("test/comp", source).issues]


def _by_rule(source: str, rule: str):
    return [i for i in lint_component("test/comp", source).issues if i.rule == rule]


CLEAN_COMPONENT = (
    "{# @prop variant:select['a', 'b'] | default:\"a\" | description:\"x\" #}\n"
    '{# @prop count:number | default:0 | description:"y" #}\n'
    '{# @prop loading:boolean | default:False | description:"z" #}\n'
    '{# @prop title:text | default:"hi" | description:"q" #}\n'
    '<c-vars variant="a" count=0 loading=False title="hi" />\n'
    "<div>{{ slot }}</div>\n"
)


class TestCleanComponent:
    def test_no_issues(self):
        report = lint_component("test/clean", CLEAN_COMPONENT)
        assert report.is_clean
        assert report.issues == ()


class TestOrphanAnnotation:
    def test_prop_without_cvars_entry_is_orphan(self):
        source = '{# @prop ghost:text | default:"" | description:"q" #}\n<c-vars />\n'
        issues = _by_rule(source, "orphan-annotation")
        assert len(issues) == 1
        assert issues[0].prop_name == "ghost"
        assert issues[0].severity == "error"


class TestMissingAnnotation:
    def test_cvars_attr_without_prop_is_warning(self):
        source = '<c-vars extra="x" />\n'
        issues = _by_rule(source, "missing-annotation")
        assert len(issues) == 1
        assert issues[0].prop_name == "extra"
        assert issues[0].severity == "warning"

    def test_carries_paste_ready_stub(self):
        source = '<c-vars name="hello" />\n'
        issue = _by_rule(source, "missing-annotation")[0]
        # Default text type is inferred for string values; stub is a single
        # @prop line ready to paste above the <c-vars> tag.
        assert issue.suggestion is not None
        assert issue.suggestion.startswith("{# @prop name:text")
        assert 'default:"hello"' in issue.suggestion
        assert 'description:""' in issue.suggestion

    def test_stub_infers_boolean(self):
        source = "<c-vars active=False />\n"
        issue = _by_rule(source, "missing-annotation")[0]
        assert "active:boolean" in issue.suggestion
        assert "default:False" in issue.suggestion

    def test_stub_infers_number(self):
        source = "<c-vars count=42 />\n"
        issue = _by_rule(source, "missing-annotation")[0]
        assert "count:number" in issue.suggestion
        assert "default:42" in issue.suggestion

    def test_stub_preserves_dynamic_prefix(self):
        source = '<c-vars :items="[]" />\n'
        issue = _by_rule(source, "missing-annotation")[0]
        assert issue.suggestion.startswith("{# @prop :items:")

    def test_stub_omits_default_for_bare_attr(self):
        source = "<c-vars title />\n"
        issue = _by_rule(source, "missing-annotation")[0]
        assert "default:" not in issue.suggestion


class TestMissingCVars:
    def test_props_without_cvars_tag(self):
        source = '{# @prop x:text | default:"y" | description:"z" #}\n'
        rules = _rules(source)
        assert "missing-cvars" in rules


class TestDefaultMismatch:
    def test_text_default_diverges(self):
        source = (
            '{# @prop variant:text | default:"a" | description:"x" #}\n<c-vars variant="b" />\n'
        )
        issues = _by_rule(source, "default-mismatch")
        assert len(issues) == 1
        assert "`a`" in issues[0].message
        assert "`b`" in issues[0].message

    def test_no_mismatch_when_cvars_is_bare(self):
        # Bare attr in <c-vars> means "no explicit default" — should NOT be
        # reported as a mismatch even if @prop has a default.
        source = '{# @prop title:text | default:"hi" | description:"x" #}\n<c-vars title />\n'
        issues = _by_rule(source, "default-mismatch")
        assert issues == []


class TestDynamicPrefixMismatch:
    def test_colon_only_on_prop(self):
        source = '{# @prop :items:text | default:"[]" | description:"x" #}\n<c-vars items="[]" />\n'
        issues = _by_rule(source, "dynamic-prefix-mismatch")
        assert len(issues) == 1

    def test_colon_only_on_cvars(self):
        source = '{# @prop items:text | default:"[]" | description:"x" #}\n<c-vars :items="[]" />\n'
        issues = _by_rule(source, "dynamic-prefix-mismatch")
        assert len(issues) == 1


class TestEnumDefaultOutOfRange:
    def test_prop_default_not_in_options(self):
        source = (
            "{# @prop tone:select['info', 'danger'] | default:\"WRONG\" | description:\"x\" #}\n"
            '<c-vars tone="info" />\n'
        )
        issues = _by_rule(source, "enum-default-out-of-range")
        # Two issues: one for @prop default, one for <c-vars> if its value
        # is also outside (not the case here — `info` is valid). One firing.
        assert len(issues) == 1
        assert "WRONG" in issues[0].message


class TestRequiredWithDefault:
    def test_both_flags_present(self):
        source = (
            '{# @prop label:text | required | default:"Click" | description:"x" #}\n'
            '<c-vars label="Click" />\n'
        )
        issues = _by_rule(source, "required-with-default")
        assert len(issues) == 1
        assert issues[0].severity == "error"


class TestMissingDescription:
    def test_prop_without_description_warning(self):
        source = '{# @prop x:text | default:"y" #}\n<c-vars x="y" />\n'
        issues = _by_rule(source, "missing-description")
        assert len(issues) == 1
        assert issues[0].severity == "warning"


class TestTypeDefaultMismatch:
    def test_number_with_non_numeric_default(self):
        source = (
            '{# @prop count:number | default:"abc" | description:"x" #}\n<c-vars count="abc" />\n'
        )
        issues = _by_rule(source, "type-default-mismatch")
        assert any("number" in i.message for i in issues)

    def test_boolean_with_ambiguous_default(self):
        source = (
            '{# @prop active:boolean | default:"maybe" | description:"x" #}\n'
            '<c-vars active="maybe" />\n'
        )
        issues = _by_rule(source, "type-default-mismatch")
        assert any("boolean" in i.message for i in issues)

    def test_boolean_true_is_accepted(self):
        source = (
            '{# @prop active:boolean | default:True | description:"x" #}\n<c-vars active=True />\n'
        )
        issues = _by_rule(source, "type-default-mismatch")
        assert issues == []

    def test_number_int_is_accepted(self):
        source = '{# @prop count:number | default:5 | description:"x" #}\n<c-vars count=5 />\n'
        issues = _by_rule(source, "type-default-mismatch")
        assert issues == []

    def test_number_float_is_accepted(self):
        source = '{# @prop ratio:number | default:1.5 | description:"x" #}\n<c-vars ratio=1.5 />\n'
        issues = _by_rule(source, "type-default-mismatch")
        assert issues == []


class TestUndeclaredTemplateVar:
    def test_var_not_in_cvars_is_hint(self):
        # `undeclared-template-var` is a HEURISTIC — context-processor vars
        # and {% with %} locals legitimately trip it. So it's classified
        # as a `hint` (not `warning`) and it does NOT subtract from the
        # Insights health score.
        source = "<c-vars />\n<div>{{ mystery }}</div>\n"
        issues = _by_rule(source, "undeclared-template-var")
        assert len(issues) == 1
        assert issues[0].severity == "hint"
        assert issues[0].prop_name == "mystery"

    def test_var_in_cvars_is_ok(self):
        source = '<c-vars title="x" />\n<div>{{ title }}</div>\n'
        issues = _by_rule(source, "undeclared-template-var")
        assert issues == []

    def test_slot_and_attrs_are_reserved(self):
        source = "<c-vars />\n<div {{ attrs }}>{{ slot }}</div>\n"
        issues = _by_rule(source, "undeclared-template-var")
        assert issues == []

    def test_django_request_user_etc_are_reserved(self):
        source = (
            "<c-vars />\n<div>{{ request.path }} {{ user.username }} {{ LANGUAGE_CODE }}</div>\n"
        )
        issues = _by_rule(source, "undeclared-template-var")
        assert issues == []

    def test_for_loop_variable_is_a_local(self):
        source = '<c-vars items="[]" />\n{% for item in items %}{{ item }}{% endfor %}\n'
        issues = _by_rule(source, "undeclared-template-var")
        assert issues == []

    def test_with_block_variable_is_a_local(self):
        source = '<c-vars />\n{% with foo="bar" %}{{ foo }}{% endwith %}\n'
        issues = _by_rule(source, "undeclared-template-var")
        assert issues == []

    def test_named_slot_is_recognized(self):
        # Named slots are introduced via `@slot:name` annotations and used
        # as `{{ name }}` in the template body.
        source = (
            "{# @slot:actions <button>Save</button> — Top-right actions #}\n"
            "<c-vars />\n"
            "<div>{{ actions }}</div>\n"
        )
        issues = _by_rule(source, "undeclared-template-var")
        assert issues == []

    def test_var_inside_django_comment_is_ignored(self):
        source = "<c-vars />\n{# Documentation example: {{ ignored }} #}\n<div>ok</div>\n"
        issues = _by_rule(source, "undeclared-template-var")
        assert issues == []


class TestIssueShape:
    def test_orphan_has_line_or_none(self):
        # orphan-annotation has no associated cvar entry, so line should be None
        source = '{# @prop ghost:text | default:"" | description:"x" #}\n<c-vars />\n'
        issue = _by_rule(source, "orphan-annotation")[0]
        assert issue.component_path == "test/comp"
        assert issue.prop_name == "ghost"

    def test_required_with_default_reports_line(self):
        source = (
            '{# @prop label:text | required | default:"x" | description:"y" #}\n'
            '<c-vars label="x" />\n'
        )
        issue = _by_rule(source, "required-with-default")[0]
        assert issue.line == 1


class TestReport:
    def test_severity_buckets(self):
        source = (
            # 1 error, 1 warning
            '{# @prop ghost:text | default:"" | description:"x" #}\n<c-vars extra="x" />\n'
        )
        report = lint_component("test/comp", source)
        assert len(report.errors) >= 1
        assert len(report.warnings) >= 1
        assert report.is_clean is False


class TestMalformedPropFilter:
    def test_unescaped_quote_in_default_is_flagged(self):
        # Raw inner quotes make the segment unparseable — before this rule
        # the default was silently dropped with no trace.
        source = (
            '{# @prop greeting:text | default:"Say "hello" now" | description:"d" #}\n'
            '<c-vars greeting="x" />\n'
        )
        issues = _by_rule(source, "malformed-prop-filter")
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "default" in issues[0].message

    def test_malformed_head_is_flagged(self):
        source = '{# @prop garbage-no-type | description:"d" #}\n<c-vars x="1" />\n'
        issues = _by_rule(source, "malformed-prop-filter")
        assert len(issues) == 1
        assert issues[0].severity == "error"

    def test_clean_component_not_flagged(self):
        assert _by_rule(CLEAN_COMPONENT, "malformed-prop-filter") == []

    def test_escaped_quotes_are_valid_not_flagged(self):
        source = (
            '{# @prop greeting:text | default:"Say \\"hi\\"" | description:"d" #}\n'
            "<c-vars greeting='Say \"hi\"' />\n"
        )
        assert _by_rule(source, "malformed-prop-filter") == []

    def test_pipe_inside_quotes_not_flagged(self):
        source = (
            '{# @prop size:text | default:"md" | description:"sm | md | lg" #}\n'
            '<c-vars size="md" />\n'
        )
        assert _by_rule(source, "malformed-prop-filter") == []


class TestUnknownPropFilter:
    def test_typo_filter_key_is_flagged(self):
        source = '{# @prop x:text | default:"a" | descripton:"typo" #}\n<c-vars x="a" />\n'
        issues = _by_rule(source, "unknown-prop-filter")
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "descripton" in issues[0].message

    def test_known_filters_not_flagged(self):
        assert _by_rule(CLEAN_COMPONENT, "unknown-prop-filter") == []


class TestQuotedValueRoundTrip:
    def test_no_default_mismatch_with_single_quoted_cvars(self):
        # Escaped annotation default must compare equal to the raw value of
        # a single-quoted <c-vars> attribute (the builder's output pair).
        source = (
            '{# @prop greeting:text | default:"Say \\"hi\\"" | description:"d" #}\n'
            "<c-vars greeting='Say \"hi\"' />\n"
        )
        assert _by_rule(source, "default-mismatch") == []
        assert _by_rule(source, "orphan-annotation") == []


class TestStubSuggestionRoundTrip:
    def test_missing_annotation_stub_with_quoted_value_is_parseable(self):
        # The ready-to-paste @prop stub the linter suggests must survive its
        # own parser — including when the <c-vars> value contains quotes.
        from django_cotton_gallery.core.annotations import AnnotationParser

        source = "<c-vars greeting='Say \"hi\"' />\n"
        issues = _by_rule(source, "missing-annotation")
        assert len(issues) == 1
        stub = issues[0].suggestion
        assert stub is not None
        prop = AnnotationParser().parse(stub + '\n<c-vars x="1" />').props[0]
        assert prop.clean_name == "greeting"
        assert prop.default == 'Say "hi"'
        assert prop.has_default is True
