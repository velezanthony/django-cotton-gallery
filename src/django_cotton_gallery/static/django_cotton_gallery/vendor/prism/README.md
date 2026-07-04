# Prism (vendored)

Syntax highlighting for the gallery's source/preview/slot-editor surfaces.
Vendored locally so highlighting works offline and isn't tied to a CDN.

- **Version**: 1.29.0 (pinned)
- **License**: MIT — © Lea Verou and contributors (https://prismjs.com)
- **Source**: https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/

## Files

| File | Purpose |
|---|---|
| `prism.min.js` | Core + `markup` (HTML, delegates `<script>`→JS / `<style>`→CSS) |
| `prism-markup-templating.min.js` | Dependency for template languages |
| `prism-django.min.js` | Django/Cotton template tags (`{% %}`, `{{ }}`, `{# #}`) |
| `prism-tomorrow.min.css` | Base token theme (the gallery overrides tag/attr colors in `preview.css`) |

The gallery's own HTMX / Alpine / Cotton token grammar lives in
`../../js/prism-cotton-stack.js` — NOT here (it's ours, not Prism's).

## Updating

Re-download the four files from the cdnjs URL above at the new version and
bump the version here. Keep it pinned; the gallery's custom grammar targets
the `markup`/`django` token structure.
