"""Gallery views — thin orchestration over factory-built services."""

from __future__ import annotations

from django.conf import settings as django_settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import get_language

from .conf import discover_template_roots, load
from .context_processors import PACKAGE_LANGUAGES
from .core.catalog import CatalogService
from .core.catalog.resolver import ComponentNotFound, resolve
from .core.catalog.scanner import signature
from .core.component_graph import build_graph, scan_external_users
from .core.insights import compute_insights
from .core.linter import lint_catalog, lint_component, lint_summary
from .core.path_safety import UnsafePath
from .core.schemas import ComponentSummary, SummaryCatalog
from .core.source_reader import read_text
from .factories import get_catalog_service, get_parser, get_preview_service
from .setup_check import check_setup, has_blocking_errors

# Lint-summary cache keyed by the catalog `signature()` — the same cheap
# `(count, max_mtime)` snapshot the catalog itself uses to invalidate.
# Editing any component mutates mtime → signature changes → cache miss →
# fresh scan. Dev-safe: the user never sees stale lint badges.
# Keeps last entry only; clearing on miss keeps memory bounded.
_lint_summary_cache: dict[tuple[int, float], dict[str, tuple[int, int, int]]] = {}


def _cached_lint_summary(catalog: CatalogService) -> dict[str, tuple[int, int, int]]:
    sig = signature(catalog.config)
    cached = _lint_summary_cache.get(sig)
    if cached is not None:
        return cached
    items = catalog.sources()
    fresh = lint_summary(items)
    _lint_summary_cache.clear()
    _lint_summary_cache[sig] = fresh
    return fresh


def _summary_catalog(catalog: CatalogService) -> SummaryCatalog:
    """Project the catalog to `ComponentSummary` — the source-free shape the
    templates render. Keeps the ~130 component sources out of the template
    context (and thus out of Debug Toolbar's per-render snapshot, which would
    otherwise retain ~385 MB/request and OOM-kill the dev server).
    """
    return {
        cat: {
            sub: [ComponentSummary(c.name, c.path, c.tag_path, c.description) for c in comps]
            for sub, comps in subcats.items()
        }
        for cat, subcats in catalog.get_catalog().items()
    }


# Rendered sidebar-tree HTML, keyed by (signature, language). The tree has no
# per-page state, so one render serves every navigation until a file changes.
_sidebar_tree_cache: dict[tuple[tuple[int, float], str | None], SafeString] = {}


def _cached_sidebar_tree(catalog: CatalogService) -> SafeString:
    """Render the sidebar category tree once per (signature, language), cached.

    The tree is 130+ nested includes. Rendered inline on every page, Debug
    Toolbar's Templates panel snapshots each one per request, and browsing
    detail pages piles that up until OOM. Pre-rendering to a single cached
    string means the toolbar sees one variable, not the whole tree.
    """
    sig = signature(catalog.config)
    key = (sig, get_language())
    cached = _sidebar_tree_cache.get(key)
    if cached is not None:
        return cached
    html = render_to_string(
        "django_cotton_gallery/_sidebar_tree.html",
        {
            "categories": _summary_catalog(catalog),
            "lint_summary": _cached_lint_summary(catalog),
        },
    )
    _sidebar_tree_cache.clear()
    _sidebar_tree_cache[key] = mark_safe(html)  # our own template output
    return _sidebar_tree_cache[key]


def _sidebar_context(catalog: CatalogService) -> dict:
    """Context every view needs to render the sidebar correctly.

    `sidebar_tree` is the pre-rendered (cached) category tree. `categories`
    (source-free `ComponentSummary`) stays for the footer count, empty-state
    check, and the index/compare grids that still iterate it.
    """
    return {
        "categories": _summary_catalog(catalog),
        "lint_summary": _cached_lint_summary(catalog),
        "sidebar_tree": _cached_sidebar_tree(catalog),
    }


TEMPLATE_INDEX = "django_cotton_gallery/index.html"
TEMPLATE_DETAIL = "django_cotton_gallery/detail.html"
TEMPLATE_DOCS = "django_cotton_gallery/docs.html"
TEMPLATE_GET_STARTED = "django_cotton_gallery/get-started.html"
TEMPLATE_RAW = "django_cotton_gallery/raw.html"
TEMPLATE_COMPARE = "django_cotton_gallery/compare.html"
TEMPLATE_LINT = "django_cotton_gallery/lint.html"
TEMPLATE_BUILDER = "django_cotton_gallery/builder.html"
TEMPLATE_INSIGHTS = "django_cotton_gallery/insights.html"
TEMPLATE_SETUP_GUIDE = "django_cotton_gallery/setup_guide.html"


def _render_setup_guide(request: HttpRequest, issues: list) -> HttpResponse:
    """Render the standalone first-run setup page.

    Activates ?lang=XX in-process before rendering — we cannot rely on
    LocaleMiddleware or set_language URL because the consumer's i18n
    setup may not exist yet. The activation lasts only for this
    response (Django resets it after).
    """
    from django.utils.translation import activate, get_language

    valid = {code for code, _name in PACKAGE_LANGUAGES}
    requested = request.GET.get("lang")
    if requested in valid:
        activate(requested)
    return render(
        request,
        TEMPLATE_SETUP_GUIDE,
        {
            "issues": issues,
            "LANGUAGE_CODE": get_language(),
            "lang_choices": PACKAGE_LANGUAGES,
        },
    )


def index(request: HttpRequest) -> HttpResponse:
    # First-run / misconfigured surface: detect blocking setup issues
    # BEFORE touching the catalog service (which would raise
    # ImproperlyConfigured deep inside, showing a Django error page
    # instead of an actionable guide). Warnings let the catalog flow
    # continue and surface alongside the empty state.
    issues = check_setup()
    if has_blocking_errors(issues):
        return _render_setup_guide(request, issues)

    catalog = get_catalog_service()
    ctx = _sidebar_context(catalog)
    # Truthful onboarding: when the catalog is empty, the empty state shows
    # the actual configured subfolder + the absolute path the gallery is
    # scanning. Hardcoding "templates/cotton/" lies whenever the consumer
    # set COTTON_DIR to anything else.
    if not ctx["categories"]:
        cfg = catalog.config
        ctx["onboarding"] = {
            "cotton_subfolder": load().cotton_subfolder,
            "cotton_dir_abs": cfg.cotton_dir.as_posix(),
            "cotton_dir_exists": cfg.cotton_dir.exists(),
        }
    # Non-blocking warnings (e.g. missing context_processor) — surface
    # them on the empty/index page so the user can fix without hunting.
    if issues:
        ctx["setup_warnings"] = issues
    return render(request, TEMPLATE_INDEX, ctx)


def docs(request: HttpRequest) -> HttpResponse:
    return render(request, TEMPLATE_DOCS, _sidebar_context(get_catalog_service()))


def get_started(request: HttpRequest) -> HttpResponse:
    return render(request, TEMPLATE_GET_STARTED, _sidebar_context(get_catalog_service()))


def _split_component_path(component_path: str) -> tuple[str, str, str]:
    """Split a catalog path into `(name, category, subcategory)`.

    `atoms/forms/input` → `("input", "atoms", "forms")`. A loose component
    with no category folder (`button`) yields `("button", "", "")`.
    """
    parts = component_path.split("/")
    name = parts[-1]
    category = parts[0] if len(parts) > 1 else ""
    subcategory = "/".join(parts[1:-1])
    return name, category, subcategory


def _has_snake_case_mismatch(component_path: str) -> bool:
    """The component's filename has a hyphen while Cotton is in snake-case mode.

    Cotton then resolves the underscore version of the template, which doesn't
    exist, and the preview fails with a cryptic `TemplateDoesNotExist`. The
    detail template surfaces a banner linking to /insights/ so the user
    understands what's wrong.
    """
    leaf = component_path.rsplit("/", 1)[-1]
    return "-" in leaf and bool(getattr(django_settings, "COTTON_SNAKE_CASED_NAMES", True))


def component_detail(request: HttpRequest, component_path: str) -> HttpResponse:
    catalog = get_catalog_service()
    try:
        _, tag_path, source = catalog.read_component(component_path)
    except (UnsafePath, ComponentNotFound) as exc:
        raise Http404(str(exc)) from exc
    parsed = get_parser().parse(source)
    name, category, subcategory = _split_component_path(component_path)
    items = catalog.sources()
    known_tags = frozenset(p.replace("/", ".") for p, _ in items)
    lint_report = lint_component(component_path, source, known_tags=known_tags)
    graph = build_graph(items)
    deps_uses, deps_used_by = graph.for_component(component_path)
    # Transitive trees — same data the direct lists show, walked recursively
    # so the user can see the full impact chain when planning a refactor.
    # Cycle-aware and depth-capped so the rendered HTML stays bounded.
    deps_uses_tree = graph.transitive_uses(component_path)
    deps_used_by_tree = graph.transitive_used_by(component_path)
    # External-users scan is opt-in. When the consumer has not enabled
    # DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS the gallery never reads code
    # outside its own catalog — so the detail page just shows an empty
    # external list and the template surfaces a "not enabled" notice.
    deps_external: tuple[str, ...] = ()
    scan_enabled = load().scan_external_users
    if scan_enabled:
        external_map = scan_external_users(
            catalog_paths=[p for p, _ in items],
            scan_roots=discover_template_roots(),
            exclude_root=catalog.config.cotton_dir,
        )
        deps_external = external_map.get(component_path, ())
    return render(
        request,
        TEMPLATE_DETAIL,
        {
            "component_name": name,
            "component_path": component_path,
            "category": category,
            "subcategory": subcategory,
            "tag_path": tag_path,
            "description": parsed.description,
            "source": source,
            "auto_props": parsed.props,
            "slots": parsed.slots,
            "has_slots": parsed.has_slots,
            "accepts_attrs": parsed.accepts_attrs,
            "strict": parsed.strict,
            "ignore_unused": parsed.ignore_unused,
            "lint": lint_report,
            "deps_uses": deps_uses,
            "deps_used_by": deps_used_by,
            "deps_external": deps_external,
            "deps_uses_tree": deps_uses_tree,
            "deps_used_by_tree": deps_used_by_tree,
            "deps_total": len(deps_uses) + len(deps_used_by) + len(deps_external),
            "external_scan_enabled": scan_enabled,
            "snake_case_mismatch": _has_snake_case_mismatch(component_path),
            **_sidebar_context(catalog),
        },
    )


def compare(request: HttpRequest) -> HttpResponse:
    """Side-by-side comparison of two components.

    Reads `?a=<path>&b=<path>` and renders both as preview cards. Each card
    has its OWN props/slots/attrs controls (the components have unrelated
    APIs, so syncing them would be heuristic and confusing). The chrome
    controls — viewport and background — are shared at the toolbar.
    """
    catalog = get_catalog_service()

    def _resolve(path: str) -> dict | None:
        if not path:
            return None
        try:
            _, tag_path, source = catalog.read_component(path)
        except (UnsafePath, ComponentNotFound):
            return None
        parsed = get_parser().parse(source)
        parts = path.split("/")
        return {
            "name": parts[-1],
            "path": path,
            "tag_path": tag_path,
            "description": parsed.description,
            "auto_props": parsed.props,
            "slots": parsed.slots,
            "has_slots": parsed.has_slots,
            "accepts_attrs": parsed.accepts_attrs,
        }

    a = _resolve(request.GET.get("a", "").strip())
    b = _resolve(request.GET.get("b", "").strip())

    partial = request.GET.get("partial", "").strip()
    if partial in ("a", "b"):
        return render(
            request,
            "django_cotton_gallery/_compare_panel.html",
            {
                "side": partial,
                "comp": a if partial == "a" else b,
            },
        )

    return render(
        request,
        TEMPLATE_COMPARE,
        {
            "a": a,
            "b": b,
            "pickers": (("a", a), ("b", b)),
            **_sidebar_context(catalog),
        },
    )


def builder(request: HttpRequest) -> HttpResponse:
    """Annotation builder — interactive form for composing `@prop` lines.

    Pure UI page. The form's logic lives in JS (live preview); the view
    just renders the static markup with the catalog so the sidebar links
    keep working.
    """
    return render(request, TEMPLATE_BUILDER, _sidebar_context(get_catalog_service()))


def lint(request: HttpRequest) -> HttpResponse:
    """Annotation lint report for the whole catalog.

    Walks every component in the catalog, runs the linter, and renders a
    grouped report. Components with zero issues collapse so the user's
    eye lands on the broken ones.
    """
    catalog = get_catalog_service()
    items = catalog.sources()
    report = lint_catalog(items)
    return render(
        request,
        TEMPLATE_LINT,
        {
            "report": report,
            **_sidebar_context(catalog),
        },
    )


def insights(request: HttpRequest) -> HttpResponse:
    """Catalog Health dashboard — aggregate metrics across the catalog.

    Four metrics are catalog-only and always available: stats top, lint
    health, deprecated components, coverage gaps. Two metrics (zombies
    and most-referenced) require scanning consumer templates and are
    only computed when `DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS` is True.
    Otherwise the page surfaces a "locked — opt in to enable" panel.
    """
    catalog_service = get_catalog_service()
    catalog = catalog_service.get_catalog()
    items = catalog_service.sources()
    graph = build_graph(items)

    scan_enabled = load().scan_external_users
    external_map: dict[str, tuple[str, ...]] | None = None
    if scan_enabled:
        external_map = scan_external_users(
            catalog_paths=[p for p, _ in items],
            scan_roots=discover_template_roots(),
            exclude_root=catalog_service.config.cotton_dir,
        )

    report = compute_insights(
        catalog=catalog,
        items=items,
        parser=get_parser(),
        scan_enabled=scan_enabled,
        used_by_map=graph.used_by,
        external_map=external_map,
    )
    # Cotton-config health check — surfaced in the dashboard so the user
    # learns about mismatches inside the gallery instead of staring at a
    # cryptic "TemplateDoesNotExist" on a single component preview. The
    # gallery itself doesn't care about the setting; Cotton does. This
    # block just inventories what the user has and flags the one combo
    # that actually breaks (kebab filenames + COTTON_SNAKE_CASED_NAMES=True).
    snake_cased = bool(getattr(django_settings, "COTTON_SNAKE_CASED_NAMES", True))
    components_with_hyphen = tuple(path for path, _ in items if "-" in path.rsplit("/", 1)[-1])
    cfg = catalog_service.config
    cotton_health = {
        "snake_cased": snake_cased,
        "components_with_hyphen": components_with_hyphen,
        "hyphen_count": len(components_with_hyphen),
        "has_mismatch": snake_cased and bool(components_with_hyphen),
        # Truthful path the gallery is scanning RIGHT NOW. Mirrors what the
        # empty-state surfaces — the user can copy/paste it to verify.
        "cotton_dir_abs": cfg.cotton_dir.as_posix(),
        "cotton_subfolder": load().cotton_subfolder,
    }
    return render(
        request,
        TEMPLATE_INSIGHTS,
        {
            "report": report,
            "scan_enabled": scan_enabled,
            "cotton_health": cotton_health,
            **_sidebar_context(catalog_service),
        },
    )


def props_index(request: HttpRequest) -> JsonResponse:
    """Bulk props/slots/attrs metadata for every component — search index.

    Lazy-fetched by the quick switcher (Ctrl+K / Cmd+K) the first time the user
    issues a structured query (e.g. `prop:size`, `accepts-attrs`). Catalog
    cache is hot at this point so the parser pass is the only cost.
    """
    catalog = get_catalog_service()
    items = catalog.sources()
    parser = get_parser()
    out = {}
    for path, source in items:
        parsed = parser.parse(source)
        out[path] = {
            "props": [
                {
                    "name": p.clean_name,
                    "type": p.type,
                    "options": list(p.options),
                    "deprecated": bool(p.deprecated),
                }
                for p in parsed.props
                if not p.hidden
            ],
            # Named slot identifiers — fuels the `slot:NAME` switcher filter.
            "slots": [s.name for s in parsed.slots if s.name],
            "accepts_attrs": parsed.accepts_attrs,
            # `has_slots` covers BOTH default (unnamed) and named slots —
            # a component can have at most one default slot plus any number
            # of named slots. The two flags below let the switcher tell
            # them apart for `has-named-slots` / `has-default-slot` filters.
            "has_slots": parsed.has_slots,
            "has_named_slots": any(s.name for s in parsed.slots),
            "has_default_slot": any(s.name is None for s in parsed.slots),
            "deprecated": any(p.deprecated for p in parsed.props),
            # Fuels the `strict` switcher filter — closed prop set (@strict).
            "strict": parsed.strict,
            # Fuels the `ignore-unused` switcher filter (@ignore-unused).
            "ignore_unused": parsed.ignore_unused,
        }
    return JsonResponse(out)


def component_preview(request: HttpRequest, component_path: str) -> JsonResponse:
    """Live preview JSON — html + cotton tag string for the detail page."""
    try:
        _, tag_path, source = get_catalog_service().read_component(component_path)
    except (UnsafePath, ComponentNotFound) as exc:
        raise Http404(str(exc)) from exc
    parsed = get_parser().parse(source)
    rendered_html, cotton_str = get_preview_service().render_live(
        request,
        tag_path,
        parsed,
        request.GET,
    )
    return JsonResponse({"html": rendered_html, "tag": cotton_str})


def component_props(request: HttpRequest, component_path: str) -> JsonResponse:
    """JSON props metadata for the slot-editor intellisense."""
    try:
        _, _tag_path, source = get_catalog_service().read_component(component_path)
    except (UnsafePath, ComponentNotFound) as exc:
        raise Http404(str(exc)) from exc
    parsed = get_parser().parse(source)
    return JsonResponse(
        {
            "props": [
                {
                    "name": p.name,
                    "clean_name": p.clean_name,
                    "type": p.type,
                    "default": p.default
                    if not isinstance(p.default, bool)
                    else ("True" if p.default else "False"),
                    "options": list(p.options),
                    "description": p.description,
                    "required": p.required,
                    "deprecated": p.deprecated,
                }
                for p in parsed.props
                if not p.hidden
            ],
            "accepts_attrs": parsed.accepts_attrs,
        }
    )


def component_raw(request: HttpRequest, component_path: str) -> HttpResponse:
    """Render a component standalone with the consumer's full asset stack — no gallery chrome."""
    try:
        _, tag_path, source = get_catalog_service().read_component(component_path)
    except (UnsafePath, ComponentNotFound) as exc:
        raise Http404(str(exc)) from exc
    parsed = get_parser().parse(source)
    rendered_html, cotton_str = get_preview_service().render_live(
        request,
        tag_path,
        parsed,
        request.GET,
    )
    return render(
        request,
        TEMPLATE_RAW,
        {
            "component_path": component_path,
            "cotton_str": cotton_str,
            "component_html": rendered_html,
        },
    )


def component_thumb(request: HttpRequest, component_path: str) -> HttpResponse:
    """Default-prop thumbnail with ETag + mtime cache."""
    catalog = get_catalog_service()
    try:
        file_path, tag_path = resolve(catalog.config.cotton_dir, component_path)
    except (UnsafePath, ComponentNotFound) as exc:
        raise Http404(str(exc)) from exc

    try:
        mtime = file_path.stat().st_mtime
    except OSError:
        mtime = 0.0

    etag = f'W/"{component_path}-{int(mtime * 1000)}"'
    if etag in request.META.get("HTTP_IF_NONE_MATCH", ""):
        response = HttpResponse(status=304)
        response["ETag"] = etag
        response["Cache-Control"] = "no-cache, must-revalidate"
        return response

    source = read_text(file_path)
    parsed = get_parser().parse(source)
    rendered_html = get_preview_service().render_thumb(request, tag_path, parsed, mtime)
    response = HttpResponse(rendered_html)
    response["ETag"] = etag
    response["Cache-Control"] = "no-cache, must-revalidate"
    return response
