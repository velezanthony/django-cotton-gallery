# django-cotton-gallery

[![Tests](https://github.com/velezanthony/django-cotton-gallery/actions/workflows/test.yml/badge.svg)](https://github.com/velezanthony/django-cotton-gallery/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/velezanthony/django-cotton-gallery/branch/main/graph/badge.svg)](https://codecov.io/gh/velezanthony/django-cotton-gallery)
[![PyPI](https://img.shields.io/pypi/v/django-cotton-gallery.svg)](https://pypi.org/project/django-cotton-gallery/)
[![Python](https://img.shields.io/pypi/pyversions/django-cotton-gallery.svg)](https://pypi.org/project/django-cotton-gallery/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Drop-in playground for your [django-cotton](https://django-cotton.com/) components — annotate them once with `@prop` comments and get a live, themable, copy-and-paste gallery with auto-generated controls, a lint report, and an insights dashboard.

📚 **Docs:** <https://velezanthony.github.io/django-cotton-gallery/>

![Gallery index](https://raw.githubusercontent.com/velezanthony/django-cotton-gallery/main/docs/assets/screenshot-index.png)

## Install (≈60 seconds)

The gallery is a **development-only** tool, so the recommended install is as a dev dependency with [`uv`](https://docs.astral.sh/uv/) — that way it never ships to production (`uv sync --no-dev` leaves it out):

```bash
uv add --dev django-cotton-gallery
```

Prefer pip? That works just as well:

```bash
pip install django-cotton-gallery
```

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "django_cotton",            # already there if cotton is set up
    "django_cotton_gallery",
]
```

```python
# urls.py
from django.conf import settings
from django.urls import include, path

urlpatterns = [...]

# Gate it — the gallery exposes component source code. Do NOT ship to prod.
if settings.DEBUG:
    urlpatterns += [path("", include("django_cotton_gallery.urls"))]
```

Run your server and open **`http://localhost:8000/django-cotton-gallery/`**. That's it — the gallery indexes whatever cotton already finds. The empty state walks you through your first component if the catalog is empty.

> Need production access patterns (staff-only, feature flags), asset injection, or per-setting reference? → **[Getting started](https://velezanthony.github.io/django-cotton-gallery/users/getting-started/)** · **[Configuration](https://velezanthony.github.io/django-cotton-gallery/users/configuration/)**

## What you get

**Live playground** — every component renders with auto-generated controls from your `@prop` annotations. Tweak any prop in real time, copy the tag, done.

![Component detail with live controls](https://raw.githubusercontent.com/velezanthony/django-cotton-gallery/main/docs/assets/screenshot-detail.png)

**Lint report** — three severity tiers (errors, warnings, hints) for `@prop`/`<c-vars>` mismatches, missing descriptions, and undeclared variables. The same engine runs in CI as `python manage.py cotton_lint`.

![Lint report](https://raw.githubusercontent.com/velezanthony/django-cotton-gallery/main/docs/assets/screenshot-lint.png)

**Insights dashboard** — config health, annotation coverage, zombie components, most-referenced ranking. Spot rot before it ships.

![Insights dashboard](https://raw.githubusercontent.com/velezanthony/django-cotton-gallery/main/docs/assets/screenshot-insights.png)

**Ctrl+K switcher** with structured filters (`prop:size`, `slot:actions`, `accepts-attrs`, `has-named-slots`, `deprecated`) — find any component without leaving the keyboard.

![Command palette switcher](https://raw.githubusercontent.com/velezanthony/django-cotton-gallery/main/docs/assets/screenshot-switcher.png)

Plus: a **refactor planner** (transitive dependency tree), an **annotation builder** (form-based `@prop` editor), a **side-by-side compare** view, and **i18n** chrome (English, Spanish, Basque, French). → **[Full feature tour](https://velezanthony.github.io/django-cotton-gallery/users/features/)**

## Compatibility

| | Versions |
|---|---|
| Python | 3.10 · 3.11 · 3.12 · 3.13 |
| Django | 4.2 LTS · 5.0 · 5.1 · 5.2 LTS · 6.0 |
| i18n | English (default) · Spanish · Basque · French |

CI verifies every valid Python × Django combination on every push (plus Windows + macOS smoke tests).

## Contributing & local development

Clone, then `make dev && make serve` to run the bundled demo at `http://localhost:8000/django-cotton-gallery/`. Everything else — repo layout, tests, the Python × Django matrix, i18n, releases — lives in **[docs/contributors/](https://velezanthony.github.io/django-cotton-gallery/contributors/)**. See also [CONTRIBUTING.md](./CONTRIBUTING.md) and the [CHANGELOG](./CHANGELOG.md).

## Support

[![Sponsor](https://img.shields.io/github/sponsors/velezanthony?logo=githubsponsors&color=EA4AAA)](https://github.com/sponsors/velezanthony)

If this project saves you time, consider [sponsoring its development](https://github.com/sponsors/velezanthony). It helps keep it maintained.

## License

MIT — see [LICENSE](./LICENSE).
