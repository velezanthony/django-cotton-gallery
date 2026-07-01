"""Minimal Django settings for the test suite. Independent from the demo project."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = "test-only-not-secret"
DEBUG = False
ALLOWED_HOSTS = ["*"]
USE_TZ = True
USE_I18N = True
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
    ("eu", "Euskara"),
    ("fr", "Français"),
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django_cotton",
    "django_cotton_gallery",
]

# Required: without an explicit STATIC_URL the live-server test handler
# parses None and ends up with bytes `b''` for `base_url.path`, which then
# crashes `_should_handle` when comparing to the str path of the request.
STATIC_URL = "/static/"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django_cotton.cotton_loader.Loader",
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                ),
            ],
            "builtins": ["django_cotton.templatetags.cotton"],
        },
    },
]

COTTON_SNAKE_CASED_NAMES = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
