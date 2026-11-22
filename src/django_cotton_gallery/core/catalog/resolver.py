"""Resolve a component identifier ('atoms/button') to a safe filesystem path.

Pure — uses `path_safety` for the security checks; no Django imports.
"""

from __future__ import annotations

from pathlib import Path

from ..path_safety import resolve_within, validate_segments

INDEX_FILENAME = "index.html"


class ComponentNotFound(LookupError):
    """Raised when the component file does not exist on disk."""


def resolve(cotton_dir: Path, component_path: str) -> tuple[Path, str]:
    """Return (file_path, tag_path) for the given component identifier.

    Lookup order matches Cotton's loader and `scanner.scan()`: `<path>.html`
    first, then `<path>/index.html`. When both exist the sibling file wins.
    Every candidate must stay inside `cotton_dir`.

    Raises:
        UnsafePath: segment validation or root-containment failed.
        ComponentNotFound: the resolved file does not exist.
    """
    parts = component_path.split("/")
    validate_segments(parts)

    base = cotton_dir.joinpath(*parts)
    for candidate in (base.with_suffix(".html"), base / INDEX_FILENAME):
        resolve_within(cotton_dir, candidate)
        if candidate.is_file():
            return candidate, ".".join(parts)
    raise ComponentNotFound(component_path)
