# Annotation reference

Every annotation is a Django comment block: `{# @keyword body #}`. The parser ignores everything else, so annotations can sit anywhere in the file.

## `@description`

A one-line summary used by the index card and the detail page header.

```html
{# @description Primary action button #}
```

Only the first `@description` in the file is read.

## `@prop`

Declares a controllable prop. Pipe-style filters, like Django template filters.

```html
{# @prop name:type[options] | filter1:value | filter2 | ... #}
```

### Types

| Type | Renders as | Example |
|---|---|---|
| `text` | text input | `{# @prop label:text \| default:"Click" #}` |
| `number` | number input | `{# @prop count:number \| default:5 #}` |
| `boolean` | checkbox | `{# @prop loading:boolean \| default:False #}` |
| `select['a', 'b']` | dropdown | `{# @prop variant:select['primary', 'secondary'] \| default:"primary" #}` |

### Dynamic props (colon prefix)

If the prop is meant to be passed dynamically (`:count="5"` rather than `count="5"`), prefix the name with a colon. The gallery preserves the colon when generating the tag string.

```html
{# @prop :count:number | default:5 #}
```

### Filters

| Filter | Effect | Example |
|---|---|---|
| `default` | Default value. Strings quoted, booleans/numbers unquoted. | `\| default:"primary"` |
| `description` | Help text shown in the controls. | `\| description:"Style variant"` |
| `required` | Mark as required (no default). Mutually exclusive with `default`. | `\| required` |
| `deprecated` | Show a deprecation message. | `\| deprecated:"Use 'variant' instead"` |
| `hidden` | Hide from controls (still passed if defaulted). | `\| hidden` |
| `example` | Suggested value shown in placeholder. | `\| example:"bg-brand"` |

### Boolean coercion

For `boolean` props, the parser accepts these as `True`: `True`, `true`, `1`, `on`. Anything else is `False`. This matches what HTML form checkboxes send.

### `default` wins over `required`

If you write both, `default` wins:

```html
{# @prop x:text | default:"hi" | required #}
```

The `required` flag is dropped because there's already a default. This matches the `<c-vars>` semantics and avoids contradictions.

## `@slot`

Declares a slot. The default (unnamed) slot:

```html
{# @slot Click me #}
```

A named slot (use `@slot:name`):

```html
{# @slot:actions <button>Save</button> #}
```

### Slot description (em-dash separator)

Add a description after a literal ` — ` (space + em-dash + space):

```html
{# @slot Click me — Button label #}
{# @slot:actions <button>Save</button> — Top-right action buttons #}
```

A slot that has no default content but does have a description:

```html
{# @slot:breadcrumb — Breadcrumb fragment, no default #}
```

## `@trigger`

For components that are triggered by another element (modals, drawers, popovers). The trigger renders together with the component in the preview.

```html
{# @trigger <button>Open</button> — opens the drawer #}
```

## Pass-through `attrs`

The gallery auto-detects components that pass user-supplied HTML attrs through (`{{ attrs }}` in the body, or `:attrs="attrs"` on a child component). When detected, the controls panel shows an extra "Extra attrs" textarea.

Any `name`, `name="value"`, or `name='value'` token is accepted. Event handlers (`onclick`, `onmouseover`, etc.) are silently dropped — gallery URLs are shareable, and a malicious link with `onclick="alert(1)"` would execute on the recipient's machine.

## Full example

```html
{# templates/cotton/molecules/section-card.html #}
{# @description Card with title, optional actions, and a body slot #}
{# @prop title:text | required | description:"Section heading" #}
{# @prop tone:select['neutral', 'info', 'warn'] | default:"neutral" | description:"Color tone" #}
{# @prop dismissible:boolean | default:False | description:"Show close button" #}
{# @slot Card body — Main content area #}
{# @slot:actions — Top-right action buttons (e.g. 'New', 'Filter') #}
{# @slot:footer <hr><small>Footer</small> — Optional footer #}

<c-vars title tone="neutral" dismissible=False />

<section class="card card--{{ tone }}" {{ attrs }}>
  <header class="card__head">
    <h2>{{ title }}</h2>
    {{ actions }}
    {% if dismissible %}<button class="card__close">&times;</button>{% endif %}
  </header>
  <div class="card__body">{{ slot }}</div>
  {% if footer %}<footer class="card__foot">{{ footer }}</footer>{% endif %}
</section>
```

The gallery reads:

- One **description** for the card.
- Three **props**: `title` (required text), `tone` (select with three options), `dismissible` (boolean).
- Three **slots**: default body, named `actions` and `footer`.
- **`accepts_attrs`** is `True` (the body uses `{{ attrs }}`), so the controls show the extra-attrs textarea.

## Lint rules and severity tiers

The `/django-cotton-gallery/lint/` page cross-checks every component's `@prop` annotations against its `<c-vars>` declaration. The `/django-cotton-gallery/insights/` dashboard turns those issues into a health score using these weights:

| Severity | Score weight | What it means |
|---|---|---|
| `error` | −5 each | Blocking — the prop won't reach the template as documented. |
| `warning` | −1 each | Discipline — fixable, real issue (missing description, undocumented cvar, etc.). |
| `hint` | 0 (does not subtract) | Heuristic — may produce false positives (e.g. context-processor variables). Surfaced for transparency, not for grading. |

### Rules

| Rule | Severity | Trigger |
|---|---|---|
| `orphan-annotation` | error | `@prop foo` exists but `<c-vars>` doesn't declare `foo`. |
| `dynamic-prefix-mismatch` | error | `:` prefix on one side only (`@prop :foo` vs `<c-vars foo=...>`). |
| `default-mismatch` | error | `@prop default` differs from the `<c-vars>` value. |
| `required-with-default` | error | `\| required` and `\| default:` coexist (contradictory). |
| `enum-default-out-of-range` | error | Default not in `select['…']` options. |
| `type-default-mismatch` | error | Default value doesn't match the declared type (e.g. `number` with `"abc"`). |
| `missing-cvars` | warning | Component has `@prop` but no `<c-vars>` tag. |
| `missing-annotation` | warning | `<c-vars>` declares a prop with no `@prop` documenting it. |
| `missing-description` | warning | `@prop` without `\| description:` filter. |
| `undeclared-template-var` | hint | `{{ x }}` referenced but not in `<c-vars>`. Heuristic — context-processor variables and `{% with %}` locals legitimately trip this. |
