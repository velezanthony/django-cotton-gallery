"""Resolve a component identifier ('atoms/button') to a safe filesystem path.

Pure — uses `path_safety` for the security checks; no Django imports.
"""

from __future__ import annotations

from pathlib import Path

from ..path_safety import resolve_within, validate_segments


class ComponentNotFound(LookupError):
    """Raised when the component file does not exist on disk."""


def resolve(cotton_dir: Path, component_path: str) -> tuple[Path, str]:
    """Return (file_path, tag_path) for the given component identifier.

    Raises:
        UnsafePath: segment validation or root-containment failed.
        ComponentNotFound: the resolved file does not exist.
    """
    parts = component_path.split("/")
    validate_segments(parts)

    candidate = cotton_dir.joinpath(*parts).with_suffix(".html")
    resolve_within(cotton_dir, candidate)

    if not candidate.exists():
        raise ComponentNotFound(component_path)
    return candidate, ".".join(parts)
