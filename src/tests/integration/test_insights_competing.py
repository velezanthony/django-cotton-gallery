"""Insights: the "Competing components" card and the catalog breakdown.

When `<dir>.html` and `<dir>/index.html` both exist, Cotton serves the
sibling and the dashboard warns that they compete (GitHub issue #19).
"""

from __future__ import annotations

import re

import pytest
from django.test import Client

INDEX_SOURCE = (
    "{# @description Pill via index #}\n"
    '{# @prop label:text | default:"Hi" | description:"Label" #}\n'
    '<c-vars label="Hi" />\n'
    '<span class="pill-from-index" {{ attrs }}>{{ label }}</span>\n'
)


def _text(html: str) -> str:
    """Tag-stripped, whitespace-collapsed page text."""
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


@pytest.fixture
def index_component(gallery_setup):
    """Add `cotton/pill/index.html` (index-only, no sibling)."""
    folder = gallery_setup / "cotton" / "pill"
    folder.mkdir()
    (folder / "index.html").write_text(INDEX_SOURCE)
    return folder


@pytest.fixture
def client(gallery_setup):
    return Client()


def _card(body: str, card_id: str) -> str:
    """HTML of the `<article id="...">` card, up to its closing tag."""
    start = body.index(f'id="{card_id}"')
    return body[start : body.index("</article>", start)]


def _add_conflict(cotton, name: str) -> None:
    (cotton / f"{name}.html").parent.mkdir(parents=True, exist_ok=True)
    (cotton / f"{name}.html").write_text("x")
    (cotton / name).mkdir(parents=True, exist_ok=True)
    (cotton / name / "index.html").write_text("x")


class TestInsightsCompetingComponentsCard:
    """Conflicts get their own list card, always rendered, outside the
    Cotton config card."""

    def test_card_renders_empty_state_without_conflicts(self, client, index_component):
        body = client.get("/django-cotton-gallery/insights/").content.decode("utf-8")
        card = _card(body, "competing-components")
        assert (
            "cg-insight-card--list"
            in body[body.rindex("<article", 0, body.index('id="competing-components"')) :]
        )
        assert "Competing 0" in _text(card)
        assert 'cg-insight-card__count">0<' in card
        assert 'class="cg-insight-card__empty"' in card
        assert "No components are competing." in card
        assert "cg-insight-card--warn" not in body

    def test_card_lists_conflicts(self, client, gallery_setup):
        _add_conflict(gallery_setup / "cotton", "atoms/button")
        response = client.get("/django-cotton-gallery/insights/")
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        card = _card(body, "competing-components")
        assert 'cg-insight-card__count">1<' in card
        assert "No components are competing." not in card
        assert 'href="/django-cotton-gallery/atoms/button/"' in card
        # The row shows only the component; the files live in its tooltip.
        assert "Used atoms/button.html · ignored atoms/button/index.html" in _text(card)
        assert 'class="cg-insight-card__path cg-insight-card__conflict cg-info"' in card
        assert 'role="tooltip"' in card
        assert "cg-insight-card--warn" in body

    def test_card_counts_multiple_conflicts(self, client, gallery_setup):
        cotton = gallery_setup / "cotton"
        _add_conflict(cotton, "atoms/button")
        _add_conflict(cotton, "card")
        card = _card(
            client.get("/django-cotton-gallery/insights/").content.decode("utf-8"),
            "competing-components",
        )
        assert 'cg-insight-card__count">2<' in card
        assert "Used card.html · ignored card/index.html" in _text(card)

    def test_card_follows_coverage_gaps_card(self, client, gallery_setup):
        """DOM order puts it in the free grid cell after Coverage gaps."""
        body = client.get("/django-cotton-gallery/insights/").content.decode("utf-8")
        gaps = body.index("Coverage gaps")
        competing = body.index('id="competing-components"')
        external = body.index("cg-insight-card--external")
        assert gaps < competing < external
        assert body.count("<article", gaps, competing) == 1

    def test_config_card_has_no_conflict_list(self, client, gallery_setup):
        _add_conflict(gallery_setup / "cotton", "atoms/button")
        body = client.get("/django-cotton-gallery/insights/").content.decode("utf-8")
        config = _card(body, "cotton-config")
        assert "index.html" not in config
        assert "competing" not in config.lower()
        assert 'id="index-conflicts"' not in body


class TestInsightsCatalogBreakdown:
    def test_root_level_components_get_a_label(self, client, index_component):
        body = client.get("/django-cotton-gallery/insights/").content.decode("utf-8")
        assert 'breakdown-label"></span>' not in body
        assert 'breakdown-label">Components</span>' in body
        assert 'breakdown-label">atoms</span>' in body

    def test_root_label_translates_to_spanish(self, client, index_component):
        response = client.get("/django-cotton-gallery/insights/", HTTP_ACCEPT_LANGUAGE="es")
        assert 'breakdown-label">Componentes</span>' in response.content.decode("utf-8")
