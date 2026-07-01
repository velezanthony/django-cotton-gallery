# Configuration

Every setting the gallery reads from `settings.py`. All of them are optional.

## Component discovery

### `DJANGO_COTTON_GALLERY_EXCLUDED_CATEGORIES`

Top-level category folders to hide from the gallery without deleting them.

```python
DJANGO_COTTON_GALLERY_EXCLUDED_CATEGORIES = ["icons", "experimental"]
```

### `DJANGO_COTTON_GALLERY_CATEGORY_ORDER`

Manual order for categories in the sidebar. Categories not listed here appear after, sorted alphabetically.

```python
DJANGO_COTTON_GALLERY_CATEGORY_ORDER = ["atoms", "molecules", "organisms", "layouts"]
```

### `DJANGO_COTTON_GALLERY_CATEGORY_SORT`

Sort mode for categories *not* in the manual order list. `"asc"` (default) or `"desc"`.

```python
DJANGO_COTTON_GALLERY_CATEGORY_SORT = "asc"
```

### `DJANGO_COTTON_GALLERY_SUBCATEGORY_ORDER`

Manual order for subcategories, per category.

```python
DJANGO_COTTON_GALLERY_SUBCATEGORY_ORDER = {
    "atoms": ["form", "ui", "feedback"],
    "molecules": ["navigation", "content"],
}
```

### `DJANGO_COTTON_GALLERY_SUBCATEGORY_SORT`

Sort mode for subcategories *not* in the per-category manual order. `"asc"` (default) or `"desc"`.

```python
DJANGO_COTTON_GALLERY_SUBCATEGORY_SORT = "asc"
```

## Enabling the language switcher

The gallery ships with translations for English, Spanish, Basque, and French. The dropdown in the sidebar footer only appears when your project has Django's i18n URL and middleware wired — without them, Django can't persist the chosen language, so the gallery hides the control to avoid a dead button.

Two changes in your project to enable it:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    # ... your real app URLs
]
```

```python
# settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # ← add this
    'django.middleware.common.CommonMiddleware',
    # ... rest as you had it
]
```

`LocaleMiddleware` must come **after** `SessionMiddleware` and **before** `CommonMiddleware`. Refresh the page after the changes and the dropdown shows up in the sidebar with the four supported locales.

### When `LANGUAGES` is restricted

The dropdown always shows the four locales the gallery ships translations for. **Selecting a locale only persists** between pages if Django's `LocaleMiddleware` accepts it — and `LocaleMiddleware` accepts only what's in `settings.LANGUAGES`.

If you haven't set `LANGUAGES` in your `settings.py`, Django's default list contains all 80+ supported locales (including English, Spanish, Basque, and French) — the four work out of the box.

If you've **restricted `LANGUAGES`** (e.g. only English and your business language), you need to opt the four package locales in:

```python
# settings.py
LANGUAGES = [
    ('en', 'English'),
    ('es', 'Español'),
    ('eu', 'Euskara'),
    ('fr', 'Français'),
    # ... your own locales
]
```

Without this, the gallery's dropdown still shows the four options but selecting a locale not in `LANGUAGES` is silently dropped by `LocaleMiddleware` and the page falls back to your default.

## Asset injection

The gallery has minimal chrome of its own. Your components likely need a CSS framework, an icon library, HTMX, Alpine.js, design tokens, env keys, etc. The gallery has **two complementary mechanisms** for injecting them — both are optional, both can be used together.

!!! warning "If you use the settings approach, wire one context processor"
    The `EXTRA_CSS` / `EXTRA_JS` URLs and the dependency badges in the hero are rendered from the `cotton_gallery` template variable, which is populated by a context processor. Without it, the URLs you declare are silently ignored.

    Add `gallery_assets` to your existing `TEMPLATES[0]["OPTIONS"]["context_processors"]`:

    ```python
    # settings.py
    TEMPLATES = [
        {
            # ... your existing TEMPLATES config ...
            "OPTIONS": {
                "context_processors": [
                    # ... your existing context processors ...
                    "django_cotton_gallery.context_processors.gallery_assets",
                ],
            },
        },
    ]
    ```

    Not needed if you only use the **partial** approach (the partials are rendered through `{% maybe_include %}` and don't go through the context processor).

### Which one do I use?

| You want to add… | Use |
|---|---|
| External URL lists (CDN scripts, stylesheets) | **Settings** — `DJANGO_COTTON_GALLERY_EXTRA_CSS` / `DJANGO_COTTON_GALLERY_EXTRA_JS` |
| Inline `<script>` config (e.g. `tailwind.config = {...}`) | **Partial** — `_extra_head.html` |
| `<meta>` tags, preconnects, font preloads | **Partial** — `_extra_head.html` |
| `window.MY_API_KEY = "..."` env globals | **Partial** — `_extra_head.html` |
| Post-mount JS bridges (HTMX/Alpine init hooks) | **Partial** — `_extra_body.html` |

**Rule of thumb:** prefer the partials for inline HTML — your editor syntax-highlights it and `settings.py` stays minimal. Use the settings approach for flat URL lists you also want to surface as **dependency badges** in the hero.

### Settings — for URL lists

#### `DJANGO_COTTON_GALLERY_EXTRA_CSS`

URLs (CDN or local static) added as `<link rel="stylesheet">` to every gallery page.

```python
# settings.py
DJANGO_COTTON_GALLERY_EXTRA_CSS = [
    "https://cdn.tailwindcss.com",
    "/static/app.css",
]
```

#### `DJANGO_COTTON_GALLERY_EXTRA_JS`

URLs added as `<script src="...">` before `</body>`.

```python
# settings.py
DJANGO_COTTON_GALLERY_EXTRA_JS = [
    "https://unpkg.com/htmx.org@1.9.10",
    "https://unpkg.com/alpinejs@3.13.0/dist/cdn.min.js",
]
```

URLs you list here also feed the **dependency badge detector** in the hero — see below.

### Partials — for inline HTML

Drop these files in your project's `templates/django_cotton_gallery/` directory. The gallery picks them up automatically, no settings change needed. Both are optional.

| Partial | Where it renders | Use for |
|---|---|---|
| `_extra_head.html` | End of `<head>`, after `EXTRA_CSS` | `<meta>`, font preloads, **`tailwind.config = {...}`**, design-token CSS variables, `window.*` env globals (API keys, feature flags) |
| `_extra_body.html` | End of `<body>`, after `EXTRA_JS` | Post-mount initialization scripts (HTMX bridges, Alpine setup, anything that has to run after components mount) |

If they don't exist, the gallery silently skips them (handled by the `maybe_include` template tag — necessary because `{% include "..." ignore missing %}` was removed in Django 6).

!!! tip "Tailwind play-CDN"
    The gallery is **stack-agnostic** — it doesn't ship Tailwind, HTMX, or any frontend dependency. If you want Tailwind, inject the CDN script via `EXTRA_CSS` (or load your own bundle), then put your `tailwind.config = {...}` in `_extra_head.html`. With both wired, your config block runs **after** Tailwind initializes — that's the order Tailwind's docs require.

#### Example `_extra_head.html`

A typical project that uses Tailwind play-CDN with custom theme + an env-driven API key:

```html
{# templates/django_cotton_gallery/_extra_head.html #}
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

<script>window.__MY_API_KEY = '{{ MY_API_KEY }}';</script>

<script>
  tailwind.config = {
    theme: {
      extend: {
        colors: { brand: { 500: '#ff9d0a', 600: '#ff8500' } },
      }
    }
  };
</script>
```

Tailwind play-CDN is loaded by the gallery automatically, so your `tailwind.config` block runs **after** it initializes — that's the order Tailwind's docs require.

#### Example `_extra_body.html`

```html
{# templates/django_cotton_gallery/_extra_body.html #}
<script>
  // HTMX needs the CSRF token bridged for POST requests
  document.body.addEventListener('htmx:configRequest', (e) => {
    e.detail.headers['X-CSRFToken'] =
      document.querySelector('[name=csrfmiddlewaretoken]')?.value;
  });
</script>
```

### Dependency badges

The gallery auto-detects libraries from your `EXTRA_CSS` / `EXTRA_JS` URLs and shows them as colored badges in the hero. Detection works for:

- npm-style CDNs: unpkg, esm.sh, skypack, jsdelivr
- cdnjs (`/ajax/libs/{name}/...`)
- Subdomain CDNs (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`)
- Generic hosts (extracts the second-level domain)
- Self-hosted relative paths (uses the file stem)

No configuration needed — names and colors are derived from the URLs. Badges only show URLs from the **settings** approach (the partials are not parsed for URLs by design — if a consumer wants their inline `<script src="...">` to show up as a badge, they should also list it in `EXTRA_JS`).

## Insights & external usage scan

### `DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS`

Opt-in flag that lets the gallery scan your project's templates to find which ones import each component. **Default: `False`**.

```python
DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS = True  # explicit consent
```

When `False` (the default):

- The detail page's "External usage" section shows a "scanning is disabled" notice with a one-click hint on how to enable it.
- The Insights dashboard (`/django-cotton-gallery/insights/`) renders the catalog-only metrics (lint health, annotation coverage, deprecated, coverage gaps) and locks the zombies / most-referenced cards behind the same notice.

When `True`, the gallery walks every `.html` file under:

1. Each entry in `settings.TEMPLATES[*]['DIRS']`.
2. Each installed app's `templates/` subfolder (matching what Django's `app_directories.Loader` resolves at render time).

The walk excludes the catalog itself (`cotton/`) and ignores any `.html` whose path falls inside it. The result is cached for 5 seconds (TTL) so a burst of detail-page visits doesn't repeat the work.

What's read and exposed:

- ✅ Each consumer template is read **read-only** to look for `<c-X.Y>` references.
- ✅ Only **template paths** (e.g. `dashboard.html`) appear in the gallery UI — never file contents.
- ✅ The gallery only mounts when **you** wire the URL include in your `urls.py`. The library never reads `DEBUG` or any flag of its own — mounting is fully your decision. Whenever it detects its URLs are wired in the running process, it emits a startup `RuntimeWarning` so you never deploy it by accident.
- ❌ No content is ever sent off the machine.
- ❌ No file outside the configured template roots is touched.

This is the only setting the gallery exposes that crosses the catalog boundary. If you'd rather not scan consumer code at all, leave it at the default.

## Built-in pages

The gallery owns its own URL prefix (`/django-cotton-gallery/`), so you mount it at `""` in your urls.py: `path("", include("django_cotton_gallery.urls"))`.

| Path | What it does |
|---|---|
| `/django-cotton-gallery/` | Catalog index — every component as a card with a live thumbnail. |
| `/django-cotton-gallery/<path>/` | Detail page — preview, prop controls, slots, dependencies tab, source viewer. |
| `/django-cotton-gallery/lint/` | Annotation-lint report across the whole catalog. Errors, warnings, hints. |
| `/django-cotton-gallery/insights/` | Catalog-health dashboard — stats, lint score, annotation coverage, deprecated, coverage gaps, zombies (when scanning is on), most-referenced (idem). |
| `/django-cotton-gallery/compare/?a=&b=` | Side-by-side comparison of two components with shared viewport / background controls. |
| `/django-cotton-gallery/builder/` | Interactive `@prop` annotation composer — fill the form, copy the snippet. |
| `/django-cotton-gallery/get-started/` | In-app onboarding for first-time users. |
| `/django-cotton-gallery/docs/` | Annotation grammar + setting reference, rendered in the gallery itself. |

### Quick switcher (Ctrl+K / Cmd+K)

Press `Ctrl+K` (or `Cmd+K` on macOS) anywhere in the gallery to open a fuzzy switcher. Beyond plain name search, it understands a few token filters:

| Token | Meaning |
|---|---|
| `prop:` | Suggests every prop name in the catalog. Type more letters to narrow. |
| `prop:NAME` | Components that declare a prop matching `NAME` (substring while typing, exact once committed). |
| `prop:NAME=` | Suggests the declared values for the prop (only meaningful for `select` props). |
| `prop:NAME=VALUE` | Components where that prop has that value. |
| `slot:` | Suggests every named slot in the catalog. |
| `slot:NAME` | Components with a named slot matching `NAME`. |
| `accepts-attrs` | Components that accept `{{ attrs }}`. |
| `has-slots` | Components with at least one slot (default or named). |
| `has-named-slots` | Components with at least one named slot. |
| `has-default-slot` | Components with the unnamed default slot. |
| `deprecated` | Components with at least one deprecated prop. |

Tokens combine with each other and with free text — `button accepts-attrs` filters by both. Hint chips below the input are clickable; placeholder ones (`prop:NAME`, etc.) insert just the prefix so the autocomplete kicks in.

## Cotton settings (informational)

These settings belong to **django-cotton itself**, not to the gallery — they're cotton's contract, the gallery just reads them. The gallery indexes whatever cotton finds and works with any combination, but two of cotton's settings shape what you see in the gallery, so they're worth knowing about.

### `COTTON_SNAKE_CASED_NAMES`

```python
COTTON_SNAKE_CASED_NAMES = False  # cotton's default is True
```

Cotton's setting that decides how a tag like `<c-foo-bar />` maps to a file:

- `True` (cotton's default) → strips hyphens → looks for `foo_bar.html`
- `False` → keeps the hyphen → looks for `foo-bar.html`

The gallery handles both styles transparently — its catalog scanner indexes files by their filesystem path, and tag rendering goes through cotton, so whatever cotton resolves, the gallery shows.

The Insights page **does** surface a warning if you have hyphens in filenames AND `COTTON_SNAKE_CASED_NAMES = True` — that's the one combination cotton physically can't resolve, so the previews would fail with `TemplateDoesNotExist`. The warning is informational; the gallery itself doesn't reject the configuration.

Whichever style you pick, **be consistent across the catalog** — mixing kebab and snake within the same project gets confusing fast for both you and cotton.

### `COTTON_DIR = "cotton"`

Subfolder name (relative to `TEMPLATES[0]['DIRS'][0]`) where the gallery looks for components. Belongs to Cotton's folder convention; the gallery just reads it.

```python
COTTON_DIR = "cotton"  # default — also what the gallery's docs assume
```

Set it to anything else (`COTTON_DIR = "components"`) and the gallery will scan there instead. The empty-state page surfaces the actual configured path.
