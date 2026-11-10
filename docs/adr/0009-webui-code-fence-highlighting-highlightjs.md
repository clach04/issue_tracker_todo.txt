# ADR 0009: Web UI code-fence highlighting via vendored highlight.js

Status: accepted

Context: hash:0a7d7e68. The web UI renders markdown client-side with
vendored markdown-it (ADR-0008). Code fences (e.g. ```bash) render as
plain escaped text. The tracker corpus has one tagged fence; the user
wants fenced code highlighted.

Decision: vendor highlight.js 11.9.0 (common bundle) and integrate via
markdown-it's `highlight` option. The highlight function is called with
the language tag from the fence; if the language is unknown, it returns
empty string and markdown-it escapes the code as plain text. No
autodetection. Highlight.js is loaded on show pages only, deferred.

Alternatives:
- Prism.js: smaller, but operates on DOM elements and needs an adapter
  for markdown-it; less idiomatic.
- Hand-rolled highlighter: zero vendor cost, but limited quality and
  more maintenance.

Consequences:
- New vendored asset: tools/vendor/highlight-11.9.0.min.js (~50KB,
  MIT, cdn-release). Static whitelist extended in todo_webui.py.
- Minimal token colors in PAGE_STYLE (no external CSS file).
- todo.txt/done.txt highlighting (custom grammar) deferred to a
  separate tracker issue; same library, client-side, consistent with
  ADR-0008.
