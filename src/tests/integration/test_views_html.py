"""HTML view integration tests — index, get_started, docs, detail, raw.

Complements `test_views.py` (which only covers JSON endpoints + thumb).
Uses the `gallery_setup` fixture from `conftest.py` which builds a
temp cotton tree with one annotated component, so every page has at
least one component to render.
"""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.fixture
def client(gallery_setup):
    return Client()


class TestIndex:
    def test_returns_200(self, client):
        response = client.get("/django-cotton-gallery/")
        assert response.status_code == 200

    def test_renders_sidebar_categories(self, client):
        response = client.get("/django-cotton-gallery/")
        body = response.content.decode("utf-8")
        # The fixture creates one component under cotton/atoms/button.html
        assert "atoms" in body
        assert "button" in body

    def test_no_render_error_inline(self, client):
        response = client.get("/django-cotton-gallery/")
        body = response.content.decode("utf-8")
        assert "cg-preview-error" not in body, (
            "Index page should not contain the inline render-error marker."
        )

    def test_includes_gallery_chrome(self, client):
        response = client.get("/django-cotton-gallery/")
        body = response.content.decode("utf-8")
        # Sidebar logo + navigation hooks
        assert "cg-sidebar" in body
        assert "data-cg-search" in body

    def test_renders_dependency_badges(self, gallery_setup):
        """Badges in the hero come from the gallery_assets context processor.
        If a consumer (or our own dev settings) forgets to register that
        processor, the loop renders nothing and only the hardcoded
        "Django Cotton" badge survives — which once shipped silently.
        This test fails loudly when the wiring breaks."""
        from django.test import override_settings

        from django_cotton_gallery.factories import reset_caches

        with override_settings(
            DJANGO_COTTON_GALLERY_EXTRA_JS=[
                "https://cdn.tailwindcss.com",
                "https://unpkg.com/htmx.org@1.9.10",
            ],
        ):
            reset_caches()
            body = Client().get("/django-cotton-gallery/").content.decode("utf-8")
            reset_caches()
        # Both deps must end up rendered as `<span class="cg-badge ...">`
        # entries — substring match is fine, the names come straight from
        # the URL detector.
        assert "tailwindcss" in body
        assert "htmx.org" in body


class TestIndexEmptyState:
    """Onboarding empty state — two branches, both must surface the
    actual configured cotton subfolder + absolute path so the user can
    act on truthful info."""

    def test_no_folder_branch(self, gallery_empty_no_folder):
        client = Client()
        response = client.get("/django-cotton-gallery/")
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        # The "folder not found" branch fires when cotton_dir is missing.
        assert "Cotton folder not found" in body
        # The configured subfolder shows up in the tree example.
        assert "cotton/" in body
        # The absolute path the gallery is scanning is surfaced — not a
        # hardcoded "templates/cotton/" string. The fixture's tmp_path
        # contains "templates/cotton" so a substring match suffices.
        assert "/templates/cotton" in body

    def test_empty_folder_branch(self, gallery_empty_with_folder):
        client = Client()
        response = client.get("/django-cotton-gallery/")
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        # Folder exists → encouraging variant ("No components yet"), NOT
        # the alarming "Cotton folder not found" copy.
        assert "No components yet" in body
        assert "Cotton folder not found" not in body
        # Truthful path mentioned in the lead.
        assert "/templates/cotton" in body

    def test_translates_to_spanish(self, gallery_empty_with_folder):
        client = Client()
        response = client.get("/django-cotton-gallery/", HTTP_ACCEPT_LANGUAGE="es")
        body = response.content.decode("utf-8")
        assert "Aún no hay componentes" in body

    def test_translates_to_french(self, gallery_empty_with_folder):
        client = Client()
        response = client.get("/django-cotton-gallery/", HTTP_ACCEPT_LANGUAGE="fr")
        body = response.content.decode("utf-8")
        assert "Pas encore de composants" in body


class TestGetStarted:
    def test_returns_200(self, client):
        response = client.get("/django-cotton-gallery/get-started/")
        assert response.status_code == 200

    def test_renders_three_steps(self, client):
        response = client.get("/django-cotton-gallery/get-started/")
        body = response.content.decode("utf-8")
        # Default language (en) — the three numbered section titles
        assert "1. Install" in body
        assert "2. Use a component" in body
        assert "3. Make your own" in body

    def test_translates_to_spanish(self, client):
        response = client.get("/django-cotton-gallery/get-started/", HTTP_ACCEPT_LANGUAGE="es")
        body = response.content.decode("utf-8")
        assert "1. Instalar" in body or "De cero a tu primer componente" in body

    def test_translates_to_french(self, client):
        response = client.get("/django-cotton-gallery/get-started/", HTTP_ACCEPT_LANGUAGE="fr")
        body = response.content.decode("utf-8")
        assert "1. Installer" in body or "De zéro à votre premier composant" in body


class TestDocs:
    def test_returns_200(self, client):
        response = client.get("/django-cotton-gallery/docs/")
        assert response.status_code == 200

    def test_renders_sidebar_categories(self, client):
        # The docs page also includes the sidebar via base.html.
        response = client.get("/django-cotton-gallery/docs/")
        body = response.content.decode("utf-8")
        assert "cg-sidebar" in body


class TestComponentDetail:
    def test_returns_200_for_existing_component(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/")
        assert response.status_code == 200

    def test_returns_404_for_missing_component(self, client):
        response = client.get("/django-cotton-gallery/atoms/does-not-exist/")
        assert response.status_code == 404

    def test_returns_404_for_traversal(self, client):
        response = client.get("/django-cotton-gallery/atoms/..%2Fsecret/")
        assert response.status_code == 404

    def test_renders_tag_path(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/")
        body = response.content.decode("utf-8")
        # The detail page shows the Cotton tag string for copy-paste
        assert "atoms.button" in body

    def test_renders_props_panel(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/")
        body = response.content.decode("utf-8")
        # The fixture component declares one prop named "label"
        assert "label" in body

    def test_renders_source_code(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/")
        body = response.content.decode("utf-8")
        # The component source contains the `<c-vars>` declaration
        assert "c-vars" in body or "@prop" in body


class TestComponentRaw:
    def test_returns_200(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/raw/")
        assert response.status_code == 200

    def test_no_gallery_chrome(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/raw/")
        body = response.content.decode("utf-8")
        # The raw view explicitly does NOT include the sidebar / nav.
        assert "cg-sidebar" not in body

    def test_renders_component_html(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/raw/")
        body = response.content.decode("utf-8")
        # The fixture component renders a <button>...</button>
        assert "<button" in body

    def test_returns_404_for_missing_component(self, client):
        response = client.get("/django-cotton-gallery/atoms/does-not-exist/raw/")
        assert response.status_code == 404
