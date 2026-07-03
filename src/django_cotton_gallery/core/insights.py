"""Catalog Health / Insights — aggregate metrics across the component catalog.

Pure-domain: takes the parsed catalog and (optionally) the external-references
map as inputs and produces a structured `InsightsReport`. The view layer is
in charge of deciding whether to compute the external-references map at all
(opt-in via `DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS`).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .annotations import AnnotationParser
from .linter import ComponentReport, LintReport, lint_component
from .schemas import Catalog


@dataclass(frozen=True)
class InsightsReport:
    """A snapshot of catalog-wide health and usage metrics.

    All counts are derived from data the gallery already computes for other
    pages — the linter pass and the parser pass run once, and we tally up.
    `zombies` and `most_referenced` are only meaningful when the consumer
    has opted in to scanning their templates; otherwise they're empty.
    """

    total_components: int
    by_category: tuple[tuple[str, int], ...]
    annotated_count: int
    with_props_count: int
    with_slots_count: int
    accepts_attrs_count: int
    deprecated: tuple[str, ...]
    coverage_gaps: tuple[str, ...]
    lint_total_errors: int
    lint_total_warnings: int
    lint_total_hints: int
    lint_health_score: int
    most_referenced: tuple[tuple[str, int], ...]
    zombies: tuple[str, ...]
    scan_enabled: bool

    @property
    def lint_health_label(self) -> str:
        """Plain-language qualifier for the score. Higher is better.

        Used by the dashboard alongside the raw number so the user knows
        at a glance whether 0 (or 67, or 95) is "bad" or "good" without
        having to read the formula.
        """
        s = self.lint_health_score
        if s >= 100:
            return "clean"
        if s >= 80:
            return "healthy"
        if s >= 50:
            return "needs-attention"
        return "many-issues"

    def _pct(self, count: int) -> int:
        """Percentage of the catalog `count` covers, rounded. 0 when empty."""
        if self.total_components == 0:
            return 0
        return round(100 * count / self.total_components)

    @property
    def annotated_percent(self) -> int:
        return self._pct(self.annotated_count)

    @property
    def with_props_percent(self) -> int:
        return self._pct(self.with_props_count)

    @property
    def with_slots_percent(self) -> int:
        return self._pct(self.with_slots_count)

    @property
    def accepts_attrs_percent(self) -> int:
        return self._pct(self.accepts_attrs_count)


def compute_insights(
    catalog: Catalog,
    items: Iterable[tuple[str, str]],
    parser: AnnotationParser,
    *,
    scan_enabled: bool,
    used_by_map: Mapping[str, frozenset[str]],
    external_map: Mapping[str, tuple[str, ...]] | None = None,
) -> InsightsReport:
    """Build an `InsightsReport` from already-walked catalog data.

    The caller hands in:
      - `catalog`: the ordered nested dict from `CatalogService.get_catalog()`,
        used for total counts and category breakdowns.
      - `items`: the (path, source) pairs from `CatalogService.sources()`, reused
        instead of re-walking the FS.
      - `parser`: shared AnnotationParser singleton.
      - `scan_enabled`: when True, `external_map` is honoured for zombies
        and most-referenced; when False those metrics return empty tuples.
      - `used_by_map`: from `build_graph(items).used_by` — internal references
        within the catalog. Used regardless of `scan_enabled`.
      - `external_map`: from `scan_external_users(...)` when scanning is on.
    """
    items_list = list(items)
    total_components = sum(
        len(components) for subcats in catalog.values() for components in subcats.values()
    )

    by_cat_counter: Counter[str] = Counter()
    for category, subcats in catalog.items():
        by_cat_counter[category] = sum(len(c) for c in subcats.values())
    by_category = tuple(sorted(by_cat_counter.items(), key=lambda kv: -kv[1]))

    annotated_count = 0
    with_props_count = 0
    with_slots_count = 0
    accepts_attrs_count = 0
    deprecated: list[str] = []
    # `coverage_gaps` is the union of "missing top-level @description" and
    # "any non-hidden @prop without `| description:`". The dashboard cares
    # about a single actionable list — clicking a path lands you on the
    # detail page where the linter spells out exactly what's missing.
    coverage_gaps: list[str] = []
    # Parse each source ONCE and feed the result to both the metrics below
    # and the linter — lint_catalog would otherwise re-parse the whole
    # catalog a second time.
    lint_reports: list[ComponentReport] = []
    # Components that opted out of the zombie check via `{# @ignore-unused #}`
    # (e.g. published library components that are deliberately unreferenced here).
    ignore_unused_paths: set[str] = set()

    for path, source in items_list:
        parsed = parser.parse(source)
        if parsed.ignore_unused:
            ignore_unused_paths.add(path)
        has_desc = bool(parsed.description)
        if has_desc:
            annotated_count += 1
        # A prop counts as undocumented when it's visible (not @hidden) and
        # its `description` field is empty — same rule as the linter's
        # `missing-description` warning.
        undocumented_props = any(not p.description for p in parsed.props if not p.hidden)
        if (not has_desc) or undocumented_props:
            coverage_gaps.append(path)
        if parsed.props:
            with_props_count += 1
        if parsed.has_slots:
            with_slots_count += 1
        if parsed.accepts_attrs:
            accepts_attrs_count += 1
        if any(p.deprecated for p in parsed.props):
            deprecated.append(path)
        lint_reports.append(lint_component(path, source, parsed=parsed))

    lint_report: LintReport = LintReport(components=tuple(lint_reports))
    lint_total_errors = lint_report.total_errors
    lint_total_warnings = lint_report.total_warnings
    lint_total_hints = lint_report.total_hints
    # Health score: 100 means clean. Each error costs 5, each warning 1,
    # hints don't subtract — they're heuristic flags (e.g. context-processor
    # vars trigger `undeclared-template-var`) that produce false positives,
    # so penalising them would punish legitimate setups.
    lint_health_score = max(0, 100 - lint_total_errors * 5 - lint_total_warnings)

    if scan_enabled:
        external = external_map or {}
        ranking: list[tuple[str, int]] = []
        zombies: list[str] = []
        for path, _src in items_list:
            internal = len(used_by_map.get(path, ()))
            ext = len(external.get(path, ()))
            total = internal + ext
            ranking.append((path, total))
            if total == 0 and path not in ignore_unused_paths:
                zombies.append(path)
        ranking.sort(key=lambda kv: (-kv[1], kv[0]))
        most_referenced = tuple(rank for rank in ranking[:10] if rank[1] > 0)
        zombies_t = tuple(zombies)
    else:
        most_referenced = ()
        zombies_t = ()

    return InsightsReport(
        total_components=total_components,
        by_category=by_category,
        annotated_count=annotated_count,
        with_props_count=with_props_count,
        with_slots_count=with_slots_count,
        accepts_attrs_count=accepts_attrs_count,
        deprecated=tuple(deprecated),
        coverage_gaps=tuple(coverage_gaps),
        lint_total_errors=lint_total_errors,
        lint_total_warnings=lint_total_warnings,
        lint_total_hints=lint_total_hints,
        lint_health_score=lint_health_score,
        most_referenced=most_referenced,
        zombies=zombies_t,
        scan_enabled=scan_enabled,
    )
