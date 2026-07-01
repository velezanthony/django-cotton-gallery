"""Architectural invariants enforced as tests.

These guard the dependency rule: pure-domain modules must NEVER import
Django. The day someone adds `from django.conf import settings` to
`schemas.py` because it's "easier", this test fails the build.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# This test lives in src/tests/, so parent.parent is src/ — the package sits beside it.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "django_cotton_gallery"

# Modules that MUST stay Django-free. They define data structures, parse
# annotations, validate paths, sanitize HTML, etc. — no framework code.
# All live under `core/` after the layout refactor.
PURE_DOMAIN_MODULES = [
    "core/__init__.py",
    "core/schemas.py",
    "core/annotations.py",
    "core/cvars.py",
    "core/linter/__init__.py",
    "core/linter/_rules.py",
    "core/linter/_scanners.py",
    "core/linter/_types.py",
    "core/component_graph.py",
    "core/insights.py",
    "core/path_safety.py",
    "core/source_reader.py",
    "core/dependencies.py",
    "core/catalog/__init__.py",
    "core/catalog/scanner.py",
    "core/catalog/resolver.py",
    "core/catalog/orderer.py",
    "core/catalog/cache.py",
    "core/preview/sanitizer.py",
    "core/preview/tag_builder.py",
    "core/preview/thumb_cache.py",
]

# Modules where Django imports are EXPECTED. Listed so adding a new
# Django-touching module is a deliberate choice (add it here on purpose).
DJANGO_ALLOWED_MODULES = {
    "__init__.py",  # top-level package init (just exposes __version__)
    "apps.py",
    "conf.py",  # typed snapshot of django.conf.settings
    "urls.py",
    "views.py",
    "factories.py",
    "context_processors.py",
    "setup_check.py",  # reads settings.TEMPLATES + apps registry
    "core/preview/renderer.py",  # uses Django template engine
    "core/preview/__init__.py",  # transitively imports renderer
    "templatetags/__init__.py",
    "templatetags/catalog_tags.py",
    "management/__init__.py",  # empty namespace marker
    "management/commands/__init__.py",  # empty namespace marker
    "management/commands/cotton_lint.py",  # uses django.core.management.BaseCommand
}


def _django_imports(file_path: Path) -> list[str]:
    """Return every Django import found in a Python file (empty list = clean)."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "django" or alias.name.startswith("django."):
                    found.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "django" or module.startswith("django."):
                names = ", ".join(alias.name for alias in node.names)
                found.append(f"from {module} import {names}")
    return found


@pytest.mark.parametrize("rel_path", PURE_DOMAIN_MODULES)
def test_pure_domain_does_not_import_django(rel_path: str) -> None:
    """Each module in PURE_DOMAIN_MODULES must have zero Django imports."""
    file_path = PACKAGE_ROOT / rel_path
    assert file_path.exists(), f"Listed module not found: {rel_path}"
    imports = _django_imports(file_path)
    assert imports == [], (
        f"{rel_path} must not import Django, but found: {imports}. "
        f"Either remove the import (preferred) or move the module out of "
        f"PURE_DOMAIN_MODULES if Django is genuinely needed."
    )


def test_no_unlisted_python_module_in_package() -> None:
    """Every .py in the package must be in either PURE_DOMAIN or DJANGO_ALLOWED.

    This prevents silent introduction of new Django-touching code: any new
    module forces a deliberate decision about which side it belongs on.
    """
    listed = set(PURE_DOMAIN_MODULES) | DJANGO_ALLOWED_MODULES
    found: set[str] = set()
    for py in PACKAGE_ROOT.rglob("*.py"):
        rel = py.relative_to(PACKAGE_ROOT).as_posix()
        found.add(rel)

    unlisted = found - listed
    assert unlisted == set(), (
        f"Found unlisted module(s): {sorted(unlisted)}. "
        f"Add each to either PURE_DOMAIN_MODULES (must not import Django) "
        f"or DJANGO_ALLOWED_MODULES (Django imports allowed)."
    )
