"""URL routes for the gallery."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "django_cotton_gallery"

urlpatterns = [
    path("django-cotton-gallery/", views.index, name="index"),
    path("django-cotton-gallery/get-started/", views.get_started, name="get_started"),
    path("django-cotton-gallery/docs/", views.docs, name="docs"),
    path("django-cotton-gallery/compare/", views.compare, name="compare"),
    path("django-cotton-gallery/lint/", views.lint, name="lint"),
    path("django-cotton-gallery/insights/", views.insights, name="insights"),
    path("django-cotton-gallery/builder/", views.builder, name="builder"),
    path("django-cotton-gallery/_props-index.json", views.props_index, name="props_index"),
    path(
        "django-cotton-gallery/<path:component_path>/preview/",
        views.component_preview,
        name="component_preview",
    ),
    path(
        "django-cotton-gallery/<path:component_path>/thumb/",
        views.component_thumb,
        name="component_thumb",
    ),
    path(
        "django-cotton-gallery/<path:component_path>/raw/",
        views.component_raw,
        name="component_raw",
    ),
    path(
        "django-cotton-gallery/<path:component_path>/props/",
        views.component_props,
        name="component_props",
    ),
    path(
        "django-cotton-gallery/<path:component_path>/",
        views.component_detail,
        name="component_detail",
    ),
]
