"""Apply consumer-driven ordering to a discovered catalog.

Pure — operates on Python dicts, knows nothing about filesystems or Django.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..schemas import Catalog, CatalogConfig, Component


def order_catalog(
    raw: dict[str, dict[str, list[Component]]],
    config: CatalogConfig,
) -> Catalog:
    """Return a new catalog dict with categories and subcategories ordered per config."""
    ordered: Catalog = {}
    for cat in _apply_order(raw.keys(), config.category_order, config.category_sort):
        subs = raw[cat]
        sub_prefix = config.subcategory_order.get(cat, ())
        ordered[cat] = {
            sub: subs[sub] for sub in _apply_order(subs.keys(), sub_prefix, config.subcategory_sort)
        }
    return ordered


def _apply_order(keys: Iterable[str], manual_prefix: Iterable[str], sort_mode: str) -> list[str]:
    """Manual prefix first (filtered to keys that exist), then remaining keys sorted.

    The empty-string key — used by components that live at the root
    of cotton/ with no category folder — always sorts to the END so
    named categories (atoms, molecules, …) come first regardless of
    sort direction.
    """
    keys_set = set(keys)
    prefix_seq = list(manual_prefix)
    known = [k for k in prefix_seq if k in keys_set]
    rest_keys = {k for k in keys_set if k not in prefix_seq}
    has_uncategorized = "" in rest_keys
    rest_keys.discard("")
    rest = sorted(rest_keys, reverse=(sort_mode == "desc"))
    if has_uncategorized:
        rest.append("")
    return known + rest
