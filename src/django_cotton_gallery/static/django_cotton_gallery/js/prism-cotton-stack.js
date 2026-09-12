/*
 * prism-cotton-stack — the gallery's OWN Prism grammar layer.
 *
 * Teaches Prism about the template stack Cotton components are built with, so
 * the source / preview / slot-editor surfaces color it meaningfully:
 *   - Cotton component tags:  <c-atoms.button>       token `cotton-tag`
 *   - HTMX attributes:        hx-get, hx-target       token `htmx-attr`
 *   - Alpine attributes:      x-data, @click, :class  token `alpine-attr`
 *
 * Layers on top of prism-markup (and prism-django, which extends it), so it
 * MUST load AFTER prism.min.js + prism-markup-templating + prism-django.
 * Colors live in css/preview.css (.token.cotton-tag / .htmx-attr /
 * .alpine-attr). Grammar only here — no color decisions.
 */
(function (Prism) {
  if (!Prism || !Prism.languages || !Prism.languages.markup) return;

  const markup = Prism.languages.markup;

  // 1. HTMX + Alpine attributes. Insert BEFORE `attr-name` so these specific
  //    patterns win over markup's generic attribute match. markup tokenizes
  //    `attr-value` earlier, so these only ever match the attribute NAME —
  //    never text inside a quoted value.
  Prism.languages.insertBefore(
    'inside',
    'attr-name',
    {
      'htmx-attr': { pattern: /\bhx-[\w-]+/ },
      // x-directives, @event shorthand (@click), :bind shorthand (:class).
      'alpine-attr': { pattern: /(?:\bx-[\w.:-]+|@[\w.:-]+|:[\w.-]+)/ },
    },
    markup.tag,
  );

  // Alpine attribute VALUES (x-data="{…}", @click="…", :class="…") are
  // JavaScript expressions — inject the JS grammar into them so they highlight
  // like a real editor. Mirrors how Prism handles style=""/onclick="". The
  // attribute NAME keeps its alpine-attr color; the value body becomes JS.
  if (Prism.languages.javascript && typeof markup.tag.addAttribute === 'function') {
    markup.tag.addAttribute('x-[\\w:.-]+|@[\\w.:-]+|:[\\w.-]+', 'javascript');
    // addAttribute leaves the attribute NAME a generic attr-name; re-key it to
    // alpine-attr so the name keeps its Alpine color while the value body is JS.
    const specials = markup.tag.inside['special-attr'];
    const added = specials[specials.length - 1];
    if (added && added.inside && added.inside['attr-name']) {
      added.inside = {
        'alpine-attr': added.inside['attr-name'],
        'attr-value': added.inside['attr-value'],
      };
    }
  }

  // 2. Cotton component tags. The tag NAME lives in markup.tag.inside.tag.inside
  //    (once `punctuation` has stripped the leading `<` / `</`). Matching
  //    `c-foo.bar` there tokenizes only Cotton tags, not every HTML element.
  const tagName =
    markup.tag.inside && markup.tag.inside.tag && markup.tag.inside.tag.inside;
  if (tagName) {
    tagName['cotton-tag'] = { pattern: /c-[\w.-]+/i };
  }

  // The gallery's own annotation DSL — {# @prop name:type | default:… #},
  // {# @slot … #}, {# @description … #}, {# @trigger <markup> #}. Color its
  // parts instead of leaving it a flat comment; the CSS dims the whole token
  // (it's metadata). Inserted before django's `comment` so @-annotations win;
  // plain {# … #} comments fall through and stay green. (Multi-line
  // {% comment %} annotation blocks are a v2 — they fight Prism's
  // markup-templating engine, which extracts each {% %} before this grammar.)
  if (Prism.languages.django && Prism.languages.markup) {
    Prism.languages.insertBefore('django', 'comment', {
      'annotation': {
        pattern: /\{#\s*@[\s\S]*?#\}/,
        greedy: true,
        inside: {
          'annotation-delimiter': { pattern: /^\{#|#\}$/, alias: 'comment' },
          // @trigger injects real markup into the preview — highlight its body
          // with the full markup grammar (HTML / Alpine / HTMX / Cotton).
          'annotation-trigger': {
            pattern: /@trigger[^#]*/,
            inside: {
              'annotation-directive': { pattern: /^@trigger/, alias: 'keyword' },
              'annotation-markup': { pattern: /[\s\S]+/, inside: Prism.languages.markup },
            },
          },
          // @description / @slot are free-text prose — plain-text color; only
          // the directive keeps its keyword color.
          'annotation-doc': {
            pattern: /@(?:description|slot)(?::[\w-]+)?[^#]*/,
            inside: { 'annotation-directive': { pattern: /^@[\w:-]+/, alias: 'keyword' } },
          },
          'annotation-directive': { pattern: /@[\w-]+/, alias: 'keyword' },
          'annotation-string': {
            pattern: /(["'])(?:\\.|(?!\1)[^\\\r\n])*\1/,
            greedy: true,
            alias: 'string',
          },
          'annotation-boolean': { pattern: /\b(?:True|False|None)\b/, alias: 'boolean' },
          'annotation-filter': {
            pattern: /\b(?:default|description|required|min|max)\b(?=\s*:)/,
            alias: 'property',
          },
          'annotation-type': {
            pattern: /(:)(?:select|text|number|boolean)\b/,
            lookbehind: true,
            alias: 'class-name',
          },
          'annotation-punctuation': { pattern: /[[\]|:,]/, alias: 'punctuation' },
          'annotation-name': { pattern: /[\w-]+/, alias: 'attr-name' },
        },
      },
    });
  }

  // Python ALL_CAPS names read as constants (Django settings like INSTALLED_APPS,
  // DEBUG, …). Prism-python leaves them plain (near-white); tokenize them so the
  // palette can color them. Appended last so keywords / booleans / builtins win
  // first; the pattern only matches fully upper-case words (`\b…\b`), so mixed
  // case like `HTTPServer` is untouched.
  if (Prism.languages.python) {
    Prism.languages.python.constant = { pattern: /\b[A-Z][A-Z0-9_]*\b/ };
  }

  // Bash: Prism only colors known builtins (ls, cd, …), so a `python manage.py
  // …` invocation renders almost entirely plain — it reads as un-highlighted.
  // Color the leading command word and CLI flags so it looks like real shell.
  if (Prism.languages.bash) {
    Prism.languages.insertBefore('bash', 'comment', {
      // CLI flags first (-x, --warnings-as-errors) so `command` doesn't eat them.
      'option': { pattern: /(^|\s)--?[a-z][\w-]*/im, lookbehind: true },
      // Command words — first char is not a dash (Prism re-anchors `^` per text
      // segment, so this colors each bare word of the invocation, flags aside).
      'command': { pattern: /(^[ \t]*|[|&;]\s*)[\w./][\w./-]*/m, lookbehind: true },
    });
  }
})(window.Prism);
