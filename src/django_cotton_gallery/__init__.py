"""Django Cotton Gallery — component gallery and @prop annotation system for django-cotton."""

from importlib.metadata import PackageNotFoundError, version

try:
    # pyproject.toml is the single source of truth — a literal here drifts.
    __version__ = version("django-cotton-gallery")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0.dev0"
