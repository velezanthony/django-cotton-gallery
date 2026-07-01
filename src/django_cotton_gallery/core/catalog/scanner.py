"""Filesystem walk that discovers cotton components.

Pure — touches the filesystem but no Django imports. Configuration
arrives via `CatalogConfig`; consumers construct it from settings
elsewhere (factories layer).
"""

from __future__ import annotations

from collections.abc import Iterable

from ..annotations import AnnotationParser
from ..schemas import CatalogConfig, Component
from ..source_reader import read_text

COMPONENT_GLOB = "*.html"
PRIVATE_PREFIX = "_"
INDEX_FILENAME = "index.html"


def scan(config: CatalogConfig, parser: AnnotationParser | None = None) -> Iterable[Component]:
    """Walk `config.cotton_dir`, yield Component instances in path-sorted order.

    Index file convention: `<dir>/index.html` is treated as the canonical
    entry point for a component named `<dir>`. Cotton's loader does the
    same — `<c-atoms.button />` resolves to `atoms/button.html` first,
    then falls back to `atoms/button/index.html`. The gallery follows
    the same rule so users can pick either layout.

    Conflict: when both `<dir>.html` and `<dir>/index.html` exist, the
    sibling file wins (matches cotton's resolution order). The index
    file is silently dropped to avoid duplicate catalog entries.
    """
    if not config.cotton_dir.exists():
        return
    parser = parser or AnnotationParser()
    all_files = sorted(config.cotton_dir.rglob(COMPONENT_GLOB))
    # Set of (rel_parts) tuples for non-index components — used to
    # detect when a sibling `<dir>.html` already serves the component
    # that `<dir>/index.html` would also produce.
    sibling_paths = {
        (*f.relative_to(config.cotton_dir).parts[:-1], f.stem)
        for f in all_files
        if f.name != INDEX_FILENAME
    }

    for file in all_files:
        rel_parts = file.relative_to(config.cotton_dir).parts
        if not _should_include(rel_parts, config.excluded_categories):
            continue

        if file.name == INDEX_FILENAME and len(rel_parts) > 1:
            # `<dir>/index.html` → component named after `<dir>`.
            if rel_parts[:-1] in sibling_paths:
                # `<dir>.html` already exists — that file wins.
                continue
            name = rel_parts[-2]
            path_parts: tuple[str, ...] = rel_parts[:-1]
        else:
            name = file.stem
            path_parts = (*rel_parts[:-1], file.stem)

        source = read_text(file)
        # Components with a single path part have no category folder
        # (e.g. `cotton/button.html` or `cotton/button/index.html`).
        # Use empty string for both category and subcategory — the UI
        # surfaces them in a dedicated "no category" group.
        if len(path_parts) > 1:
            category = path_parts[0]
            subcategory = "/".join(path_parts[1:-1])
        else:
            category = ""
            subcategory = ""
        yield Component(
            name=name,
            path="/".join(path_parts),
            tag_path=".".join(path_parts),
            category=category,
            subcategory=subcategory,
            description=parser.extract_description(source),
            source=source,
        )


def signature(config: CatalogConfig) -> tuple[int, float]:
    """Cheap (count, max_mtime) snapshot used for cache invalidation.

    Counting AND mtime are both required: file deletion can DECREASE
    max_mtime (the deleted file was the newest), so mtime alone would
    let the cache serve stale data. Count catches deletions; mtime
    catches edits.
    """
    count = 0
    max_mtime = 0.0
    if not config.cotton_dir.exists():
        return (0, 0.0)
    try:
        for f in config.cotton_dir.rglob(COMPONENT_GLOB):
            rel_parts = f.relative_to(config.cotton_dir).parts
            if not _should_include(rel_parts, config.excluded_categories):
                continue
            count += 1
            m = f.stat().st_mtime
            if m > max_mtime:
                max_mtime = m
    except OSError:
        pass
    return (count, max_mtime)


def _should_include(rel_parts: tuple[str, ...], excluded_categories: frozenset[str]) -> bool:
    """The single source of truth for which components belong to the catalog.

    Used by both `scan` and `signature` so cache invalidation matches discovery.

    Components at any depth qualify, including the root of cotton/
    (e.g. `cotton/button.html`, no category folder). Categories are a
    UI organization choice, not a filesystem requirement.
    """
    if not rel_parts:
        return False
    if any(part.startswith(PRIVATE_PREFIX) for part in rel_parts):
        return False
    return rel_parts[0] not in excluded_categories


def group_by_category(components: Iterable[Component]) -> dict[str, dict[str, list[Component]]]:
    """Group a flat iterable of Components into the nested catalog shape."""
    grouped: dict[str, dict[str, list[Component]]] = {}
    for c in components:
        grouped.setdefault(c.category, {}).setdefault(c.subcategory, []).append(c)
    return grouped
