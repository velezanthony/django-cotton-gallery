"""Component dependency graph.

For each component, list:
  - `uses`            — other catalog components it references via `<c-X.Y>` tags.
  - `used_by`         — catalog components that reference IT.
  - `external_users`  — templates OUTSIDE the catalog (consumer code) that
                        reference it. Helps spot zombie components.

Useful for impact analysis before refactoring (e.g. "atoms/button is used by
N components — touch carefully"). Pure — no I/O at the module level; the
external-scan helper does file I/O but takes paths so the caller can keep
the domain logic testable.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Match `<c-foo.bar.baz>` opening tags (Cotton component references).
# `c-vars` is the variable-declaration meta-tag, not a component reference,
# so we always skip it during the scan.
_TAG_RE = re.compile(r"<c-([\w.-]+)\b")


def extract_component_uses(source: str) -> set[str]:
    """Return the set of tag paths referenced by `<c-X.Y>` in `source`.

    Tag paths use dots between subfolder segments — `atoms.button` maps
    back to the catalog path `atoms/button`.
    """
    found: set[str] = set()
    for match in _TAG_RE.finditer(source):
        tag = match.group(1)
        if tag == "vars":  # <c-vars> is the prop declaration, not a reference
            continue
        found.add(tag)
    return found


@dataclass(frozen=True)
class DepNode:
    """A single node in a transitive dependency tree.

    `is_cycle=True` marks a node that closes a cycle in the parent chain
    — its children are NOT recursed (would loop forever) and the template
    renders it with a special hint so the user understands why the branch
    stops there.

    `truncated=True` marks a node that hit the depth limit. Same semantics:
    children skipped, UI shows a "depth limit" indicator.
    """

    path: str
    children: tuple[DepNode, ...] = ()
    is_cycle: bool = False
    truncated: bool = False


@dataclass(frozen=True)
class ComponentGraph:
    """Forward + inverse dependency maps across the catalog."""

    uses: dict[str, frozenset[str]]  # path -> components it uses
    used_by: dict[str, frozenset[str]]  # path -> components that use it

    def for_component(self, path: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return `(uses, used_by)` lists for one component, sorted alphabetically."""
        return (
            tuple(sorted(self.uses.get(path, ()))),
            tuple(sorted(self.used_by.get(path, ()))),
        )

    def transitive_uses(self, path: str, *, max_depth: int = 8) -> DepNode:
        """Forward tree — what does `path` need (recursively).

        Cycles are broken by marking the offending node with `is_cycle=True`
        and not recursing through it. Depth is capped at `max_depth` to
        keep the rendered HTML bounded on pathological catalogs.
        """
        return _build_tree(path, self.uses, max_depth)

    def transitive_used_by(self, path: str, *, max_depth: int = 8) -> DepNode:
        """Reverse tree — who depends on `path` (recursively).

        Same shape as `transitive_uses`. Useful for impact analysis: if
        you change `atoms/button`, this tree shows every catalog component
        that needs re-checking, transitively.
        """
        return _build_tree(path, self.used_by, max_depth)


def _build_tree(
    root: str,
    edges: dict[str, frozenset[str]],
    max_depth: int,
) -> DepNode:
    """Recursive tree construction with cycle detection + depth limit."""

    def recurse(node: str, ancestors: tuple[str, ...], depth: int) -> DepNode:
        if depth >= max_depth:
            return DepNode(path=node, truncated=True)
        if node in ancestors:
            return DepNode(path=node, is_cycle=True)
        children = edges.get(node, frozenset())
        if not children:
            return DepNode(path=node)
        new_ancestors = (*ancestors, node)
        rendered = tuple(recurse(child, new_ancestors, depth + 1) for child in sorted(children))
        return DepNode(path=node, children=rendered)

    return recurse(root, (), 0)


def build_graph(items: Iterable[tuple[str, str]]) -> ComponentGraph:
    """Build the dependency graph from an iterable of `(path, source)` pairs.

    References are resolved from tag paths (`atoms.button`) back to canonical
    catalog paths (`atoms/button`) so callers can navigate directly. Tags
    that don't resolve to a catalog component (typos, removed components)
    and self-references are dropped.
    """
    paths: list[str] = []
    sources_by_path: dict[str, str] = {}
    for path, source in items:
        paths.append(path)
        sources_by_path[path] = source

    # tag-path -> canonical path: `atoms.button` -> `atoms/button`.
    tag_to_path = {p.replace("/", "."): p for p in paths}

    uses_map: dict[str, set[str]] = defaultdict(set)
    used_by_map: dict[str, set[str]] = defaultdict(set)

    for path in paths:
        for tag in extract_component_uses(sources_by_path[path]):
            target = tag_to_path.get(tag)
            if target is None or target == path:
                continue
            uses_map[path].add(target)
            used_by_map[target].add(path)

    return ComponentGraph(
        uses={k: frozenset(v) for k, v in uses_map.items()},
        used_by={k: frozenset(v) for k, v in used_by_map.items()},
    )


# Cache for `scan_external_users` keyed by `(catalog_paths, scan_roots,
# exclude_root, fingerprint)`. The fingerprint is a `(count, max_mtime)`
# tuple over every HTML file under the scan_roots — same pattern as the
# catalog's `signature()` helper. Editing any consumer template mutates
# mtime → fingerprint changes → cache miss → fresh walk. No TTL window;
# the gallery never serves stale external-usage data.
_scan_cache: dict[tuple, dict[str, tuple[str, ...]]] = {}


def _clear_scan_cache() -> None:
    """Test hook — flush the cache so unit tests see fresh FS state."""
    _scan_cache.clear()


def _scan_fingerprint(scan_roots: Iterable[Path]) -> tuple[int, float]:
    """`(count, max_mtime)` of every HTML file the scan would touch.

    Cheap stat-only walk — no `read_text`. Computing the fingerprint costs
    ~5-15 ms even on large template trees, so when nothing has changed we
    avoid the much heavier read pass that `scan_external_users` does on
    a cache miss.
    """
    count = 0
    max_mtime = 0.0
    for root in scan_roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if not resolved.exists():
            continue
        try:
            for f in resolved.rglob("*.html"):
                try:
                    m = f.stat().st_mtime
                except OSError:
                    continue
                count += 1
                if m > max_mtime:
                    max_mtime = m
        except OSError:
            continue
    return (count, max_mtime)


def scan_external_users(
    catalog_paths: Iterable[str],
    scan_roots: Iterable[Path],
    exclude_root: Path,
) -> dict[str, tuple[str, ...]]:
    """Find templates outside the catalog that reference each component.

    Walks every `.html` file under `scan_roots`, skipping anything inside
    `exclude_root` (the catalog itself — those refs are already covered
    by the in-catalog `used_by` map). Returns a `dict[component_path,
    tuple[template_relpath, ...]]` mapping each component to the
    templates that include it.

    Pure-domain: takes paths as arguments so the caller controls what gets
    scanned and the result is deterministic. Mtime-fingerprint cache —
    invalidates as soon as any scanned file changes.
    """
    catalog_paths_tuple = tuple(sorted(catalog_paths))
    scan_roots_list = list(scan_roots)
    scan_roots_tuple = tuple(str(p) for p in scan_roots_list)
    fingerprint = _scan_fingerprint(scan_roots_list)
    cache_key = (catalog_paths_tuple, scan_roots_tuple, str(exclude_root), fingerprint)
    cached = _scan_cache.get(cache_key)
    if cached is not None:
        return cached

    catalog_set = set(catalog_paths)
    tag_to_path = {p.replace("/", "."): p for p in catalog_set}
    exclude_resolved = exclude_root.resolve()
    out: dict[str, set[str]] = defaultdict(set)

    for root in scan_roots:
        root = root.resolve()
        if not root.exists():
            continue
        for file in root.rglob("*.html"):
            try:
                file_resolved = file.resolve()
            except OSError:
                continue
            # Skip anything inside the catalog — those references are
            # internal and already in `used_by`.
            try:
                file_resolved.relative_to(exclude_resolved)
                continue
            except ValueError:
                pass
            try:
                source = file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for tag in extract_component_uses(source):
                target = tag_to_path.get(tag)
                if target is None:
                    continue
                # Render the file path relative to its scan root for the
                # nicest display ("dashboard/views.html" instead of an
                # absolute path).
                try:
                    rel = str(file.relative_to(root))
                except ValueError:
                    rel = str(file)
                out[target].add(rel)

    result = {k: tuple(sorted(v)) for k, v in out.items()}
    _scan_cache[cache_key] = result
    return result
