"""Integration tests for view endpoints — focus on JSON / thumb routes that
don't need the gallery's HTML chrome (those are exercised in round 5)."""

import json

import pytest
from django.test import Client


@pytest.fixture
def client(gallery_setup):
    return Client()


class TestJsonEndpoints:
    def test_component_preview_returns_json(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/preview/")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "html" in data
        assert "tag" in data
        assert "c-atoms.button" in data["tag"]

    def test_component_props_returns_json(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/props/")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "props" in data
        assert "accepts_attrs" in data
        assert any(p["name"] == "label" for p in data["props"])
        assert data["accepts_attrs"] is True


class TestThumbEndpoint:
    def test_thumb_returns_html_with_etag(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/thumb/")
        assert response.status_code == 200
        assert "ETag" in response.headers
        assert response.headers["Cache-Control"] == "no-cache, must-revalidate"

    def test_thumb_returns_304_on_matching_etag(self, client):
        response = client.get("/django-cotton-gallery/atoms/button/thumb/")
        etag = response.headers["ETag"]
        response_2 = client.get(
            "/django-cotton-gallery/atoms/button/thumb/",
            HTTP_IF_NONE_MATCH=etag,
        )
        assert response_2.status_code == 304


class TestErrorHandling:
    def test_missing_component_returns_404(self, client):
        response = client.get("/django-cotton-gallery/atoms/does-not-exist/preview/")
        assert response.status_code == 404

    def test_path_traversal_returns_404(self, client):
        response = client.get("/django-cotton-gallery/atoms/..%2Fsecret/preview/")
        assert response.status_code == 404

    def test_private_component_returns_404(self, client):
        response = client.get("/django-cotton-gallery/atoms/_private/preview/")
        assert response.status_code == 404


class TestXSSReflection:
    """End-to-end regression — request.GET prop values must NOT smuggle event
    handlers into the rendered HTML. The frontend injects this output via
    `innerHTML`, so a reflected `onclick=` becomes a clickjack vector spread
    by URL-sharing (the gallery's own headline feature)."""

    def test_prop_value_does_not_inject_event_handler(self, client):
        response = client.get(
            "/django-cotton-gallery/atoms/button/preview/",
            {"label": 'a" onclick="alert(1)'},
        )
        assert response.status_code == 200
        body = json.loads(response.content)
        # The value contains `"` but no `'`, so the tag wraps it in single
        # quotes — Cotton parses the whole payload as ONE attribute value
        # (breakout would need a `'`, which that quoting branch forbids).
        assert "label='a\" onclick=\"alert(1)'" in body["tag"]
        # The rendered HTML must never carry a live handler — the payload
        # only survives autoescaped inside text/attr content (&quot;).
        assert '" onclick=' not in body["html"]
        assert 'onclick="alert' not in body["html"]
        assert "onclick='alert" not in body["html"]

    def test_prop_value_does_not_inject_script_tag(self, client):
        response = client.get(
            "/django-cotton-gallery/atoms/button/preview/",
            {"label": "<script>alert(1)</script>"},
        )
        assert response.status_code == 200
        body = json.loads(response.content)
        assert "<script>" not in body["html"]
        assert "<script>" not in body["tag"]
