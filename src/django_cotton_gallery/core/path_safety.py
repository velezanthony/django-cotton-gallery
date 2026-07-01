"""Centralized path-traversal validation.

Pure — no Django imports. Consumers map `UnsafePath` to their own error
type (Http404 in views, custom exceptions elsewhere).
"""

from __future__ import annotations

from pathlib import Path

_FORBIDDEN_SEGMENTS = frozenset({"", ".", ".."})
_FORBIDDEN_CHARS = ("\\", ":", "\x00")
_PRIVATE_PREFIX = "_"


class UnsafePath(ValueError):
    """Raised when a path-segment list or resolved path is not safe to use."""


def validate_segments(parts: list[str]) -> None:
    """Reject empty, traversal, private, or control-character segments.

    Raises `UnsafePath` on the first invalid segment.
    """
    for part in parts:
        if part in _FORBIDDEN_SEGMENTS or part.startswith(_PRIVATE_PREFIX):
            raise UnsafePath(f"invalid path segment: {part!r}")
        if any(c in part for c in _FORBIDDEN_CHARS):
            raise UnsafePath(f"invalid character in segment: {part!r}")


def resolve_within(root: Path, candidate: Path) -> Path:
    """Resolve `candidate` and verify it stays inside `root`.

    Returns the resolved candidate. Raises `UnsafePath` if the resolved
    candidate is not within the resolved root (or root itself).
    """
    try:
        resolved_candidate = candidate.resolve(strict=False)
        resolved_root = root.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise UnsafePath(f"could not resolve path: {candidate}") from exc

    if resolved_candidate == resolved_root:
        return resolved_candidate
    if resolved_root not in resolved_candidate.parents:
        raise UnsafePath(f"path escapes root: {candidate}")
    return resolved_candidate
