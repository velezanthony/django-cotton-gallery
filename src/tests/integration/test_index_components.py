"""Integration tests for `<dir>/index.html` components (GitHub issue #19).

An index-only component appears in the sidebar, so every per-component
endpoint must serve it too.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

INDEX_SOURCE = (
    "{# @description Pill via index #}\n"
    '{# @prop label:text | default:"Hi" | description:"Label" #}\n'
    '<c-vars label="Hi" />\n'
    '<span class="pill-from-index" {{ attrs }}>{{ label }}</span>\n'
)


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


@pytest.mark.usefixtures("index_component")
class TestIndexOnlyComponentEndpoints:
    def test_detail_returns_200(self, client):
        response = client.get("/django-cotton-gallery/pill/")
        assert response.status_code == 200
        assert "Pill via index" in response.content.decode("utf-8")

    def test_raw_renders_component(self, client):
        response = client.get("/django-cotton-gallery/pill/raw/")
        assert response.status_code == 200
        assert "pill-from-index" in response.content.decode("utf-8")

    def test_preview_renders_component(self, client):
        response = client.get("/django-cotton-gallery/pill/preview/")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "c-pill" in data["tag"]
        assert "pill-from-index" in data["html"]

    def test_props_endpoint(self, client):
        response = client.get("/django-cotton-gallery/pill/props/")
        assert response.status_code == 200
        assert any(p["name"] == "label" for p in json.loads(response.content)["props"])

    def test_thumb_endpoint(self, client):
        response = client.get("/django-cotton-gallery/pill/thumb/")
        assert response.status_code == 200
        assert "pill-from-index" in response.content.decode("utf-8")

    def test_compare_resolves_index_component(self, client):
        response = client.get("/django-cotton-gallery/compare/?a=pill&partial=a")
        assert response.status_code == 200
        assert 'cg-compare__panel-title">pill</h2>' in response.content.decode("utf-8")
