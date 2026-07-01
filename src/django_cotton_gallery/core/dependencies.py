"""Detect frontend dependencies from CDN asset URLs.

Names are extracted from the URL itself by recognising common CDN shapes
(npm-style packages, cdnjs paths, subdomain hosts, self-hosted file stems).
Colors are derived from a stable hash of the name so each dep keeps the
same swatch across requests without us picking it.

Pure — no Django imports.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

# Palette the chrome's CSS knows how to paint (`.cg-badge--<color>`). Adding a
# color here also requires adding a `.cg-badge--<color>` rule in gallery.css.
_COLORS: tuple[str, ...] = (
    "blue",
    "green",
    "cyan",
    "indigo",
    "purple",
    "pink",
    "orange",
    "amber",
    "gray",
)


@dataclass(frozen=True)
class Dependency:
    """A frontend dependency inferred from one of the consumer's asset URLs."""

    name: str
    color: str


def detect(urls: Iterable[str]) -> tuple[Dependency, ...]:
    """Return deduped Dependencies in first-seen order (stable badge layout)."""
    seen: dict[str, Dependency] = {}
    for url in urls:
        name = _extract_name(url)
        if not name or name in seen:
            continue
        seen[name] = Dependency(name=name, color=_color_for(name))
    return tuple(seen.values())


def _extract_name(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme in ("data", "mailto", "tel", "javascript"):
        return None

    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    if host.endswith("unpkg.com") or host.endswith("esm.sh") or host.endswith("skypack.dev"):
        return _npm_package(path.lstrip("/"))

    if host.endswith("jsdelivr.net"):
        rest = path.lstrip("/")
        if rest.startswith("npm/"):
            return _npm_package(rest[4:])
        if rest.startswith("gh/"):
            # /gh/{user}/{repo}@{branch}/{file} — the repo name identifies it
            parts = rest[3:].split("/", 2)
            return parts[1].split("@", 1)[0] if len(parts) >= 2 else None

    if host.endswith("cdnjs.cloudflare.com") and path.startswith("/ajax/libs/"):
        return path[len("/ajax/libs/") :].split("/", 1)[0] or None

    if host.startswith("cdn."):
        rest = host[4:]
        return rest.rsplit(".", 1)[0] or None

    if host:
        labels = host.split(".")
        if len(labels) >= 2:
            return labels[-2]
        return host

    if path:
        filename = path.rstrip("/").rsplit("/", 1)[-1]
        stem = filename.split(".", 1)[0]
        return stem or None

    return None


def _npm_package(rest: str) -> str | None:
    """Extract the package name from `{pkg}@{ver}/...` or `@{scope}/{pkg}@{ver}/...`."""
    if not rest:
        return None
    if rest.startswith("@"):
        scope, _, after = rest.partition("/")
        if not after:
            return scope or None
        pkg = after.split("/", 1)[0].split("@", 1)[0]
        return f"{scope}/{pkg}" if pkg else scope
    return rest.split("/", 1)[0].split("@", 1)[0] or None


def _color_for(name: str) -> str:
    # blake2b (not md5) — deterministic short hash; md5 is deprecated even
    # for non-cryptographic uses since some scanners flag it on principle.
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).hexdigest()
    return _COLORS[int(digest, 16) % len(_COLORS)]
