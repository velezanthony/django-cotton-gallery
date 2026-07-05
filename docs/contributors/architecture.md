# Architecture

How the library is laid out and why. Read this once before making structural changes.

## High-level shape

`django-cotton-gallery` is a Django reusable app. It scans a `cotton/` directory of `<c-X />` components, parses optional `@prop` annotations from each, and renders a gallery surface where each component can be browsed and previewed live with editable controls.

The package has **one public surface** (the URL config + 8 views) and **one internal pipeline** (filesystem → catalog → preview).

## Layout: package by feature, not by layer

```
src/django_cotton_gallery/
├── core/                       # Pure-domain logic (no Django imports)
│   ├── catalog/                # "Discover and resolve components"
│   ├── preview/                # "Render a component with live params"
│   ├── linter/                 # "Cross-check @prop comments against <c-vars>"
│   ├── annotations.py          # @prop / @slot parser (pure)
│   ├── schemas.py              # Frozen dataclasses (the data contract)
│   ├── path_safety.py          # Traversal validation (pure, raises UnsafePath)
│   ├── source_reader.py        # File reading with encoding fallback (pure)
│   ├── dependencies.py         # CDN URL → library name (pure)
│   ├── component_graph.py      # Component dependency graph (pure)
│   ├── cvars.py                # <c-vars> extraction (pure)
│   └── insights.py             # Cotton config health checks (pure)
├── management/commands/        # cotton_lint command
├── factories.py                # lru_cache-d service constructors
├── views.py                    # Thin orchestrators
├── urls.py                     # Routes
├── apps.py                     # AppConfig
├── conf.py                     # Setting keys + defaults
├── setup_check.py              # First-run misconfiguration checks
├── context_processors.py       # gallery_assets exposure
└── templatetags/               # Template helpers
```

**The pure domain lives under `core/`** — every module there is free of Django imports (enforced by `test_architecture.py`). **Files are single-responsibility.** When a single responsibility needs 3+ files (catalog discovery + resolution + ordering + caching), it gets a subpackage with a `__init__.py` facade (`CatalogService`).

This is **package-by-feature** ("Screaming Architecture"): the folder names tell you *what the system does*, not *what pattern it uses*. We explicitly rejected `domain/`, `application/`, `infrastructure/` as ceremony for a ~1500-line library.

## The pipeline (data flow)

```
filesystem (cotton/)
    │
    │  core/catalog/scanner.py walks files
    ▼
list[Component]                                ← core/schemas.py: Component
    │
    │  core/catalog/orderer.py applies user-defined ordering
    ▼
Catalog (nested dict by category/subcategory)  ← core/schemas.py: Catalog
    │
    │  core/catalog/cache.py memoizes by (count, max_mtime)
    ▼
[ render to index page ]


request to /cotton/atoms/button/
    │
    │  core/catalog/resolver.py validates path, returns (Path, tag_path)
    ▼
file Path + tag_path
    │
    │  core/source_reader.py reads with encoding fallback
    ▼
source string
    │
    │  core/annotations.py parses {# @prop ... #} blocks
    ▼
ParsedComponent                                ← core/schemas.py
    │
    │  core/preview/tag_builder.py composes a Cotton tag string from parsed + GET params
    ▼
"<c-atoms.button variant=\"danger\" />"
    │
    │  core/preview/sanitizer.py guards user-typed pass-through attrs (XSS)
    │  core/preview/renderer.py runs Cotton compiler + Django template engine
    ▼
rendered HTML
```

## Key decisions

### Frozen dataclasses for the contract (`core/schemas.py`)

Every value passed between the layers is an immutable dataclass: `Prop`, `Slot`, `ParsedComponent`, `Component`, `Catalog`, `GalleryAssets`, `CatalogConfig`. Frozen because:

- They're values, not entities. Mutation makes no sense.
- They're cached (in `CatalogCache`) — mutation would corrupt the cache.
- It's a self-enforcing API: callers can't accidentally hand back a modified version.

### lru_cache instead of module-level singletons (`factories.py`)

The original `geocom-cotton` codebase used a `_singletons: dict[str, object] = {}` global dict with lazy accessor functions. We replaced this with `@lru_cache(maxsize=1)` factories:

```python
@lru_cache(maxsize=1)
def get_catalog_service() -> CatalogService:
    return CatalogService(get_catalog_config(), get_parser())
```

Why this is better:

- Thread-safe out of the box.
- Cache invalidation is built in: `get_catalog_service.cache_clear()`.
- Tests that use `@override_settings` just call `reset_caches()` — no leaky `_reset_singletons()` test hook.
- No global mutable dict to reason about.

### XSS sanitizer as a pure function

`core/preview/sanitizer.py` only knows about strings. It has no Django imports, no dependencies. This means:

- Tests run without Django (microsecond-fast).
- The sanitizer can be lifted into a different project with zero changes.
- The XSS-prevention logic is reviewable in isolation, not tangled with template rendering.

The sanitizer enforces an **allow-list grammar**: only tokens matching `name`, `name="value"`, or `name='value'` survive. Event handlers (`on*`) are categorically denied. Null bytes, `<`, `>`, and unbalanced quotes are rejected.

### Path traversal validation centralized

`core/path_safety.py` exports `validate_segments` and `resolve_within`, plus an `UnsafePath` exception type. The view layer (`views.py`) catches `UnsafePath` and `ComponentNotFound` via the `_component_route` decorator and translates them to `Http404`.

This means:

- The domain modules don't import Django (they raise their own exception types).
- Path validation rules live in **one place** — adding a new check (e.g. forbidden Unicode codepoints) is a one-liner instead of hunting down 5 sites.

### Constants live with their consumer

The original codebase had a `_constants.py` god-file mixing template paths, setting keys, sort modes, file extensions, slot params, asset settings — completely unrelated concerns. We removed it. Each constant now lives in the module that uses it:

- `TRUTHY_TOKENS` → `core/annotations.py` (only the parser needs it)
- `COMPONENT_GLOB`, `PRIVATE_PREFIX` → `core/catalog/scanner.py`
- `DEFAULT_SLOT_PARAM`, `EXTRA_ATTRS_PARAM` → `core/preview/tag_builder.py`
- `SETTING_*` keys → `factories.py` and `context_processors.py`
- `TEMPLATE_*` paths → `views.py`

There was zero overlap — every constant was used by exactly one module. The "shared constants" abstraction was pure ceremony.

### Cotton compiler instantiated once per process

`core/preview/renderer.py` uses `@lru_cache(maxsize=1)` to ensure `CottonCompiler()` is built once and reused. Cotton's compiler precompiles the regex patterns it uses internally — instantiating it per request is wasted work.

### Scope boundary: rendering, not QA

The gallery's job is to **render components**. We explicitly removed the axe-core accessibility checker integration — accessibility testing belongs in the consumer's CI, not bolted into the preview chrome. If a future feature is "let me run X linter on the rendered output", reject by default.

### Highlighting: extend vendored Prism, don't fork

The Source / preview / slot surfaces are coloured by **Prism 1.29.0, vendored locally** under `static/django_cotton_gallery/vendor/prism/` (no CDN) — core + `markup-templating` + `django` + `python` + `bash` + the tomorrow theme. Our own grammar layer, `static/django_cotton_gallery/js/prism-cotton-stack.js`, teaches Prism the tokens it doesn't ship: Cotton tags (`<c-…>`), HTMX (`hx-*`) and Alpine (`x-*` / `@` / `:`) attributes (with the Alpine value re-tokenised as JavaScript), the `{# @… #}` annotation DSL, Python ALL_CAPS constants, and bash command words. The VS Code Dark+ palette lives in `css/preview.css`; the grammar file makes **no colour decisions**. A from-scratch tokeniser would reinvent JS/HTML/CSS colouring for no gain — the only thing Prism can't give us is catalog-aware *diagnostics*, and those are a separate layer (the linter), not the highlighter's job.

## What lives inside `src/` (but is NOT shipped)

All code lives under `src/`, but only `src/django_cotton_gallery/` is published. Hatchling's `packages = ["src/django_cotton_gallery"]` picks up just that subtree — the demo and the tests sit alongside it and are excluded from the wheel.

- **`src/tests/`** — the test suite. Mirrors the package layout. NOT shipped.
- **`src/demo/`** (`config/` + `manage.py` + `templates/cotton/`) — a Django demo project that depends on the library in editable mode. NOT shipped.

## What lives outside `src/`

- **`docs/`** — all documentation, built by mkdocs and deployed to GitHub Pages. Two sections: `docs/users/` (consumer-facing) and `docs/contributors/` (maintainer-facing — this folder). NOT shipped.
- **`.github/`** — CI workflows. NOT shipped.
- **`dist/`** — built wheel + sdist. NOT shipped (it's the output, not the source).
- **Root config files** — `pyproject.toml`, `Makefile`, `tox.ini`, `mkdocs.yml`, `uv.lock`, and the dotfiles. NOT shipped.

## Things that are NOT in the architecture

- No models, no migrations. The library has zero database state.
- No middleware. The consumer brings their own.
- No authentication. Component galleries are dev tools — the consumer decides who sees them (typically `DEBUG=True` only or behind staff-only middleware).
- No async. Filesystem walks and Cotton rendering are sync; for a dev-time tool the cost is negligible.
- No hot-reload of the library itself. Editing `src/` requires a server restart (Django's `runserver` does this for you in dev). Templates and static files DO reload without restart.
