"""Tests for gallery template tags and filters."""

from django.template import Context, Template

from django_cotton_gallery.core.schemas import Component
from django_cotton_gallery.templatetags.catalog_tags import (
    component_count,
    js_names,
    js_names_from_category,
    total_components,
)


def _comp(name: str, category: str = "atoms", subcategory: str = "") -> Component:
    return Component(
        name=name,
        path=f"{category}/{name}",
        tag_path=f"{category}.{name}",
        category=category,
        subcategory=subcategory,
    )


class TestComponentCount:
    def test_single_subcategory(self):
        subs = {"": [_comp("a"), _comp("b")]}
        assert component_count(subs) == 2

    def test_multiple_subcategories(self):
        subs = {"": [_comp("a")], "ui": [_comp("b"), _comp("c")]}
        assert component_count(subs) == 3

    def test_empty(self):
        assert component_count({}) == 0


class TestTotalComponents:
    def test_across_categories(self):
        cats = {
            "atoms": {"": [_comp("a")], "ui": [_comp("b"), _comp("c")]},
            "molecules": {"": [_comp("d")]},
        }
        assert total_components(cats) == 4

    def test_empty_tree(self):
        assert total_components({}) == 0


class TestJsArrays:
    def test_js_names_basic(self):
        result = str(js_names([_comp("a"), _comp("b")]))
        assert result == "['a','b']"

    def test_js_names_empty(self):
        assert str(js_names([])) == "[]"

    def test_js_names_from_category_flattens(self):
        subs = {"": [_comp("a")], "ui": [_comp("b"), _comp("c")]}
        result = str(js_names_from_category(subs))
        assert "'a'" in result
        assert "'b'" in result
        assert "'c'" in result


class TestMaybeIncludeTag:
    def test_missing_template_returns_empty(self):
        template = Template("{% load catalog_tags %}{% maybe_include 'does_not_exist.html' %}")
        rendered = template.render(Context({}))
        assert rendered == ""


class TestCodeblockTag:
    def test_escapes_html_entities(self):
        template = Template(
            "{% load catalog_tags %}{% codeblock %}<button>x</button>{% endcodeblock %}"
        )
        rendered = template.render(Context({}))
        assert "&lt;button&gt;" in rendered
        assert "<button>" not in rendered

    def test_preserves_template_syntax_with_verbatim(self):
        template = Template(
            "{% load catalog_tags %}{% codeblock %}{% verbatim %}{{ x }}{% endverbatim %}{% endcodeblock %}"
        )
        rendered = template.render(Context({}))
        assert "{{ x }}" in rendered
