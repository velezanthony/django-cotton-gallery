"""Tests for CDN URL → Dependency detection."""

import pytest

from django_cotton_gallery.core.dependencies import Dependency, _extract_name, detect


class TestDetect:
    def test_empty_input(self):
        assert detect([]) == ()

    def test_single_url(self):
        result = detect(["https://unpkg.com/htmx.org@1.9.10"])
        assert len(result) == 1
        assert result[0].name == "htmx.org"

    def test_dedupes_same_name(self):
        result = detect(
            [
                "https://unpkg.com/htmx.org@1.9.10",
                "https://unpkg.com/htmx.org@1.9.11",
            ]
        )
        assert len(result) == 1

    def test_preserves_first_seen_order(self):
        result = detect(
            [
                "https://unpkg.com/alpinejs@3.13.0",
                "https://cdn.tailwindcss.com",
                "https://unpkg.com/htmx.org@1.9.10",
            ]
        )
        names = [d.name for d in result]
        assert names == ["alpinejs", "tailwindcss", "htmx.org"]

    def test_ignores_unidentifiable_urls(self):
        result = detect(["data:text/css,body{}", "mailto:x@y.z"])
        assert result == ()

    def test_color_is_stable_for_same_name(self):
        a = detect(["https://unpkg.com/htmx.org@1"])
        b = detect(["https://unpkg.com/htmx.org@2"])
        assert a[0].color == b[0].color

    def test_returns_dependency_dataclass(self):
        result = detect(["https://unpkg.com/htmx.org@1"])
        assert isinstance(result[0], Dependency)


class TestExtractNameNpmCdns:
    def test_unpkg_simple_package(self):
        assert _extract_name("https://unpkg.com/htmx.org@1.9.10") == "htmx.org"

    def test_unpkg_scoped_package(self):
        assert _extract_name("https://unpkg.com/@hotwired/turbo@8.0.0") == "@hotwired/turbo"

    def test_unpkg_with_subpath(self):
        assert _extract_name("https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js") == "htmx.org"

    def test_esm_sh(self):
        assert _extract_name("https://esm.sh/preact@10") == "preact"

    def test_skypack(self):
        assert _extract_name("https://cdn.skypack.dev/lodash@4") == "lodash"


class TestExtractNameJsdelivr:
    def test_npm(self):
        assert _extract_name("https://cdn.jsdelivr.net/npm/htmx.org@1.9") == "htmx.org"

    def test_npm_scoped(self):
        assert (
            _extract_name("https://cdn.jsdelivr.net/npm/@floating-ui/dom@1.0") == "@floating-ui/dom"
        )

    def test_gh(self):
        assert (
            _extract_name("https://cdn.jsdelivr.net/gh/user/myrepo@main/dist/file.js") == "myrepo"
        )


class TestExtractNameCdnjs:
    def test_cdnjs(self):
        assert (
            _extract_name("https://cdnjs.cloudflare.com/ajax/libs/lodash/4.17.21/lodash.min.js")
            == "lodash"
        )


class TestExtractNameSubdomain:
    def test_cdn_subdomain(self):
        assert _extract_name("https://cdn.tailwindcss.com") == "tailwindcss"

    def test_cdn_subdomain_with_path(self):
        assert _extract_name("https://cdn.tailwindcss.com/3.4.0") == "tailwindcss"


class TestExtractNameGenericHost:
    def test_two_label_host(self):
        assert _extract_name("https://example.com/file.js") == "example"

    def test_three_label_host(self):
        assert _extract_name("https://fonts.googleapis.com/css2") == "googleapis"


class TestExtractNameSelfHosted:
    def test_relative_static_path(self):
        assert _extract_name("/static/css/app.css") == "app"

    def test_relative_no_extension(self):
        assert _extract_name("/static/js/main") == "main"


class TestExtractNameRejected:
    @pytest.mark.parametrize(
        "scheme", ["data:text/css,body{}", "mailto:x@y", "tel:+1234", "javascript:void(0)"]
    )
    def test_unsupported_schemes(self, scheme):
        assert _extract_name(scheme) is None

    def test_empty_string(self):
        assert _extract_name("") is None

    def test_non_string_input(self):
        assert _extract_name(None) is None  # type: ignore[arg-type]
        assert _extract_name(123) is None  # type: ignore[arg-type]


class TestColorPalette:
    def test_color_is_from_palette(self):
        result = detect(["https://unpkg.com/x@1", "https://unpkg.com/y@1", "https://unpkg.com/z@1"])
        palette = {"blue", "green", "cyan", "indigo", "purple", "pink", "orange", "amber", "gray"}
        for dep in result:
            assert dep.color in palette
