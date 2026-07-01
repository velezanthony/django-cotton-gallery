"""URL configuration without django.conf.urls.i18n — used to verify
the gallery renders even when the consumer has not mounted the i18n
URLs (so `set_language` cannot be reversed).
"""

from django.urls import include, path

urlpatterns = [
    path("", include("django_cotton_gallery.urls")),
]
