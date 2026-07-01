"""URL configuration for the test suite."""

from django.urls import include, path

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    # Mount the gallery at the root — the gallery owns its own URL prefix
    # (`/django-cotton-gallery/...`) so consumers don't need to namespace it.
    path("", include("django_cotton_gallery.urls")),
]
