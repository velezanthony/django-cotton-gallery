"""Tests for the Insights dashboard, props-index, and the opt-in scan setting.

The opt-in flag `DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS` is False by default so the
gallery does not read code outside its own catalog without consent. These
tests cover both states (enabled / disabled) for the detail page deps panel,
the insights page, and the props-index endpoint.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client
from django.test.utils import override_settings


@pytest.fixture
def client(gallery_setup):
    return Client()


class TestScanExternalUsersOptIn:
    """The setting defaults to False — every metric/feature that scans
    consumer templates must surface a clear "not enabled" path."""

    def test_default_is_false_and_detail_page_locks_external_panel(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/")
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        # Locked panel surfaces the setting name so the consumer knows how
        # to flip the switch — that's the contract.
        assert "DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS" in body
        # No actual external paths leaked when scanning is off.
        assert "cg-deps__list--external" not in body

    @override_settings(DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS=True)
    def test_enabled_detail_page_renders_external_users_section(self, client, gallery_setup):
        # Add a consumer template that imports the button so deps_external
        # has something to surface.
        consumer = gallery_setup / "dashboard.html"
        consumer.write_text("<c-atoms.button>Click</c-atoms.button>")
        response = client.get("/django-cotton-gallery/atoms/button/")
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        # The locked banner is gone; the actual external path is rendered.
        assert "DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS" not in body
        assert "dashboard.html" in body


class TestInsightsDashboard:
    def test_renders_with_default_setting(self, client):
        response = client.get("/django-cotton-gallery/insights/")
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        # Catalog-only metrics always render.
        assert "Catalog insights" in body or "Insights" in body
        # External-section is locked.
        assert "DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS" in body

    @override_settings(DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS=True)
    def test_renders_with_scan_enabled_unlocks_external(self, client):
        response = client.get("/django-cotton-gallery/insights/")
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        # When scanning is on the page does NOT render the locked panel.
        assert "DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS" not in body
        # The "Zombies" header still appears because the section is unlocked.
        assert "Zombies" in body

    def test_lint_and_coverage_metrics_present(self, client):
        response = client.get("/django-cotton-gallery/insights/")
        body = response.content.decode("utf-8")
        for label in ("Lint health", "Annotation coverage", "Deprecated", "Coverage gaps"):
            assert label in body, f"missing label: {label}"


class TestPropsIndex:
    """The bulk metadata endpoint backing the search-by-prop quick switcher."""

    def test_returns_dict_keyed_by_path(self, client):
        response = client.get("/django-cotton-gallery/_props-index.json")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert isinstance(data, dict)
        # Every component path appears once.
        assert "atoms/button" in data

    def test_per_component_payload_shape(self, client):
        response = client.get("/django-cotton-gallery/_props-index.json")
        data = json.loads(response.content)
        button = data["atoms/button"]
        assert "props" in button
        assert "accepts_attrs" in button
        assert "has_slots" in button
        assert "deprecated" in button
        # `strict` fuels the switcher's `strict` filter; the button isn't @strict.
        assert button["strict"] is False
        # `ignore_unused` fuels the switcher's `ignore-unused` filter.
        assert button["ignore_unused"] is False
        # The button fixture has a `label` prop so it should surface.
        assert any(p["name"] == "label" for p in button["props"])

    def test_does_not_scan_consumer_templates(self, client, gallery_setup):
        """props-index is computed from the catalog only — must work even
        when scanning is disabled (the default)."""
        # No external scan setting → should still respond fine.
        response = client.get("/django-cotton-gallery/_props-index.json")
        assert response.status_code == 200


class TestLintHealthScore:
    """The score formula MUST ignore hints. Heuristic checks like
    `undeclared-template-var` produce false positives on legitimate
    context-processor variables, so making them subtract would punish
    perfectly fine setups."""

    def test_hints_do_not_subtract(self, tmp_path):
        from django_cotton_gallery.core.annotations import AnnotationParser
        from django_cotton_gallery.core.insights import compute_insights

        # Component with a clean catalog except for a single
        # `undeclared-template-var` hint (mystery comes from a context
        # processor, not declared in <c-vars>).
        source = "{# @description Card #}\n<c-vars />\n<div>{{ mystery }}</div>\n"
        report = compute_insights(
            catalog={},
            items=[("atoms/card", source)],
            parser=AnnotationParser(),
            scan_enabled=False,
            used_by_map={},
            external_map=None,
        )
        # 1 hint exists but doesn't drag the score down — still 100.
        assert report.lint_total_hints >= 1
        assert report.lint_health_score == 100

    def test_warnings_subtract_one_each(self, tmp_path):
        from django_cotton_gallery.core.annotations import AnnotationParser
        from django_cotton_gallery.core.insights import compute_insights

        # @description present, prop annotated WITHOUT description filter →
        # exactly one `missing-description` warning.
        source = (
            "{# @description Card #}\n"
            '{# @prop label:text | default:"x" #}\n'  # missing | description:
            '<c-vars label="x" />\n'
            "<div></div>\n"
        )
        report = compute_insights(
            catalog={},
            items=[("atoms/card", source)],
            parser=AnnotationParser(),
            scan_enabled=False,
            used_by_map={},
            external_map=None,
        )
        assert report.lint_total_warnings == 1
        assert report.lint_health_score == 99


class TestCoverageGaps:
    """`coverage_gaps` is the umbrella metric the dashboard surfaces — it
    must agree with the linter's `missing-description` warning so the
    "Every component documented" empty state does NOT lie when a prop is
    annotated without `| description:`."""

    def test_prop_without_description_counted_as_gap(self, tmp_path):
        from django_cotton_gallery.core.annotations import AnnotationParser
        from django_cotton_gallery.core.insights import compute_insights

        # Component HAS a top-level @description but a prop is missing the
        # `| description:` filter — the linter flags it; insights must too.
        source = (
            "{# @description Card-like surface #}\n"
            "{# @prop variant:select['a', 'b'] | default:\"a\" #}\n"  # no description filter
            '<c-vars variant="a" />\n'
            "<div {{ attrs }}>{{ slot }}</div>\n"
        )
        catalog = {"atoms": {"": []}}  # shape only; we feed items directly
        report = compute_insights(
            catalog=catalog,
            items=[("atoms/card", source)],
            parser=AnnotationParser(),
            scan_enabled=False,
            used_by_map={},
            external_map=None,
        )
        assert "atoms/card" in report.coverage_gaps

    def test_hidden_prop_without_description_not_a_gap(self, tmp_path):
        from django_cotton_gallery.core.annotations import AnnotationParser
        from django_cotton_gallery.core.insights import compute_insights

        # Hidden props are internal API — the linter doesn't flag them and
        # neither should the coverage metric.
        source = (
            "{# @description Card-like surface #}\n"
            "{# @prop _internal:text | hidden #}\n"
            '<c-vars _internal="x" />\n'
            "<div></div>\n"
        )
        report = compute_insights(
            catalog={},
            items=[("atoms/card", source)],
            parser=AnnotationParser(),
            scan_enabled=False,
            used_by_map={},
            external_map=None,
        )
        assert report.coverage_gaps == ()

    def test_fully_documented_component_not_a_gap(self, tmp_path):
        from django_cotton_gallery.core.annotations import AnnotationParser
        from django_cotton_gallery.core.insights import compute_insights

        source = (
            "{# @description Card-like surface #}\n"
            "{# @prop variant:select['a', 'b'] | default:\"a\" | description:\"Visual style\" #}\n"
            '<c-vars variant="a" />\n'
            "<div></div>\n"
        )
        report = compute_insights(
            catalog={},
            items=[("atoms/card", source)],
            parser=AnnotationParser(),
            scan_enabled=False,
            used_by_map={},
            external_map=None,
        )
        assert report.coverage_gaps == ()


class TestComputeInsights:
    """Direct unit tests for the pure-domain `compute_insights` helper."""

    def test_zombies_empty_when_scan_disabled(self, gallery_setup):
        from django_cotton_gallery.core.insights import compute_insights
        from django_cotton_gallery.factories import get_catalog_service, get_parser

        catalog_service = get_catalog_service()
        catalog = catalog_service.get_catalog()
        items = [
            (comp.path, comp.source)
            for subcats in catalog.values()
            for comps in subcats.values()
            for comp in comps
        ]
        report = compute_insights(
            catalog=catalog,
            items=items,
            parser=get_parser(),
            scan_enabled=False,
            used_by_map={},
            external_map=None,
        )
        # Catalog-only metrics still computed.
        assert report.total_components == 1
        # External metrics gated off.
        assert report.zombies == ()
        assert report.most_referenced == ()
        assert report.scan_enabled is False

    def test_zombies_populated_when_scan_enabled(self, gallery_setup):
        from django_cotton_gallery.core.insights import compute_insights
        from django_cotton_gallery.factories import get_catalog_service, get_parser

        catalog_service = get_catalog_service()
        catalog = catalog_service.get_catalog()
        items = [
            (comp.path, comp.source)
            for subcats in catalog.values()
            for comps in subcats.values()
            for comp in comps
        ]
        report = compute_insights(
            catalog=catalog,
            items=items,
            parser=get_parser(),
            scan_enabled=True,
            used_by_map={},
            external_map={},
        )
        # The lone button has zero references in any direction → zombie.
        assert report.zombies == ("atoms/button",)
        assert report.scan_enabled is True


class TestDiscoverTemplateRoots:
    """The helper that builds the comprehensive scan_roots — TEMPLATES.DIRS
    plus per-app `templates/` subfolders. Only invoked when the consumer
    has opted in to scanning."""

    def test_includes_templates_dirs(self, gallery_setup):
        from django_cotton_gallery.conf import discover_template_roots

        roots = discover_template_roots()
        # gallery_setup configures TEMPLATES with one DIRS entry — that
        # path must appear in the roots.
        assert any(str(gallery_setup) in str(r) for r in roots)


class TestZombiesIgnoreUnused:
    """`{# @ignore-unused #}` opts a component out of the zombie check — for
    library components that are deliberately unreferenced in this workspace."""

    def test_ignore_unused_excluded_from_zombies(self):
        from django_cotton_gallery.core.annotations import AnnotationParser
        from django_cotton_gallery.core.insights import compute_insights

        # Both components have zero references; only one opts out.
        lib = "{# @ignore-unused #}\n<div></div>\n"
        orphan = "<div></div>\n"
        report = compute_insights(
            catalog={},
            items=[("atoms/lib", lib), ("atoms/orphan", orphan)],
            parser=AnnotationParser(),
            scan_enabled=True,
            used_by_map={},
            external_map={},
        )
        assert "atoms/orphan" in report.zombies
        assert "atoms/lib" not in report.zombies
