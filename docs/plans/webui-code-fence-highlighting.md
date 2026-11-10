# Web UI code-fence syntax highlighting (client-side highlight.js)

Status: done 2026-11-10 - highlight.js 11.9.0 common bundle vendored and
integrated with markdown-it; todo.txt/done.txt highlighting stays deferred
to a separate tracker issue (same library, custom grammar).

Source: hash:0a7d7e68 (from web UI markdown rendering plan
docs/plans/done/webui-markdown-rendering.md, hash:e072da96, ADR-0008).
Decision: vendor highlight.js, common bundle, lazy-loaded; integrate with
markdown-it via the `highlight` option. todo.txt/done.txt highlighting
stays deferred to a separate issue (same library, custom grammar).

## Decisions

- Library: highlight.js 11.9.0 (cdn-release build), common bundle
  (~40 languages, ~50KB minified). Vendored at
  `tools/vendor/highlight-11.9.0.min.js`, versioned filename, pinned via
  a constant in `todo_webui.py`.
- Integration: markdown-it `highlight` option in `webui.js`. When a
  language tag is present AND `hljs.getLanguage(lang)` knows it, return
  highlighted HTML; otherwise return empty string (markdown-it escapes
  the code as plain text). No autodetection of language.
- Loading: lazy. Only load highlight.js when a show page actually has a
  tagged code fence (`<pre class="md">` containing a fence). The
  bootstrap injects a `<script>` for the vendor asset on demand; the
  server always serves the highlight.js script tag only on show pages
  (same as webui.js, but with `defer` and a data attribute).
- Styling: highlight.js ships a theme CSS; the page style is inline
  (server-side). A minimal theme is added to `PAGE_STYLE` (token
  colors), no external CSS file.
- Serving: extend the `/static/<name>` whitelist with the new file.

## TODO items

- [x] Download approval + vendor `tools/vendor/highlight-11.9.0.min.js`
      (121,727 bytes, BSD-3-Clause, jsdelivr, 37 languages).
- [x] `todo_webui.py`: add highlight.js to the static whitelist, add
      script tag on show pages, add minimal token colors to `PAGE_STYLE`.
- [x] `webui.js`: pass the `highlight` option to markdown-it; guard
      against unknown languages; loaded on show pages only.
- [x] Tests: static route serves the new file; script tag present on
      show pages; token styles present.
- [x] Deferred TODO (tracker issue): todo.txt/done.txt highlighting
      (custom grammar, same library) - already tracked in hash:0a7d7e68.
