# Security Policy

## Supported versions

Security fixes are applied to the latest released version. Older versions are not patched.

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

This is a **development-only** tool with an intentionally permissive preview surface (see the threat model below). Injecting HTML, JS, or template syntax into the preview is expected behaviour, **not** a vulnerability. A real issue is one that escapes the intended surface — reading files outside the cotton component tree, or an escape that survives even when the gallery URLs are correctly gated (`if settings.DEBUG:`).

Report privately by:

1. Opening a [private security advisory](https://github.com/velezanthony/django-cotton-gallery/security/advisories/new) on GitHub, OR
2. Emailing **velezanthony2000@gmail.com** with subject `[SECURITY] django-cotton-gallery`.

Please include:

- A description of the issue and what the impact is.
- A minimal reproduction (input that triggers it, expected vs actual behaviour).
- Your name/handle for credit, if you'd like to be acknowledged.

## What to expect

- An acknowledgment within 72 hours.
- A coordinated disclosure timeline (typically 30–90 days, depending on severity).
- A fix released as a patch version with a public advisory crediting the reporter.

## How the preview works — and why it isn't sandboxed

The gallery is a **development playground**. Its preview is built on purpose so you can render components exactly as they behave in your app — including the ones that legitimately carry JavaScript, raw HTML, and framework directives (Alpine `x-*`, HTMX `hx-*`, `javascript:` URLs, inline `{% ... %}` template logic).

To make that possible, the preview pipeline **passes those inputs through as authored instead of sanitizing them**. This is a deliberate trade-off, not a defect: a playground that stripped the JavaScript out of your components could never preview an interactive component in the first place.

Concretely, this means:

- **Query-string params are rendered through Django's template engine** — so `{{ ... }}` / `{% ... %}` in a param is evaluated, exactly as it would be in a real template.
- **Slot params (`_slot`, `_slot__NAME`) are inserted as raw markup** — pass a `<script>` and it renders as a `<script>`, because your component might legitimately contain one.
- **Attribute values keep active directives** (`x-on:click`, `hx-get`, `javascript:` URLs). The attribute filter only escapes what would *accidentally* break the preview (raw `<` / `>`, unbalanced quotes, literal `on*` handlers) — it is a convenience, not a security boundary.

### Recommended: run the gallery in development only

Because the preview is permissive by design, you don't secure it by locking it down — you keep it where only you and your team work: **in development, not in production.**

The cleanest way to guarantee that with [`uv`](https://docs.astral.sh/uv/) is to install the gallery as a **development dependency**, so it never even lands in your production environment:

```bash
# Add it to the "dev" dependency group, isolated from your runtime deps
uv add --dev django-cotton-gallery
```

```toml
# pyproject.toml — uv records it here, separate from [project.dependencies]
[dependency-groups]
dev = [
    "django-cotton-gallery>=0.1",
]
```

Then sync each environment for what it needs:

```bash
uv sync              # local dev: dev group included, gallery available
uv sync --no-dev     # production build: dev group skipped, gallery absent
```

If the package isn't installed in production, its URLs and views simply don't exist there — **the surface is gone, not just gated.** That's the strongest guarantee, and it costs you nothing at runtime.

As a second, belt-and-braces layer, still wrap the URL include so the gallery stays inert even if an environment is ever built with dev deps by mistake:

```python
if settings.DEBUG:
    urlpatterns += [path("", include("django_cotton_gallery.urls"))]
```

### What still counts as a vulnerability

Since the preview is meant to be permissive, "I can inject JS / HTML / template syntax into the preview" is **expected behaviour, not a bug** — that's the feature. A genuine security issue is one that escapes the intended surface: for example, reading files **outside** the cotton component tree, or an escape that survives even when the gallery is correctly kept out of production. Those we absolutely want to hear about — see above.
