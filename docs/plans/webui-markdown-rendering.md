# Web UI markdown rendering (client-side markdown-it)

Status: done 2026-11-10 - client-side markdown-it rendering shipped; syntax highlighting deferred to tracker issue 0a7d7e68.

Source: hash:e072da96 (deferred from webui plan docs/plans/done/webui.md,
hash:51e9e387). Decision recorded in
docs/adr/0008-webui-client-side-markdown-rendering.md.

## Scope

Render `issue.md` and comment bodies as markdown in the web UI, client-side
via vendored markdown-it 14.1.0. Server keeps the escaped `<pre>` fallback.
No server-side rendering changes. No syntax highlighting (deferred).

## Decisions

- markdown-it 14.1.0 vendored at `tools/vendor/markdown-it-14.1.0.min.js`
  (123,618 bytes, MIT, already downloaded).
- Options: `markdown-it({html: false, linkify: false})`.
- Link sanitization: `http`, `https`, `mailto` only; other schemes render as
  escaped plain text.
- No-JS fallback: escaped `<pre>` (v1 behavior, unchanged).
- Delivery: `/static/<name>` route in `todo_webui.py` serving `tools/vendor/`
  with containment checks; bootstrap served from `/static/webui.js`.

## TODO items

- [x] Add `/static/<name>` route (containment, 404, Cache-Control header).
- [x] Add `/static/webui.js` bootstrap (serve the vendored bootstrap file).
- [x] Add `/static/markdown-it-14.1.0.min.js` reference (vendored asset).
- [x] Bootstrap: read each `<pre class="md">`, render with
      `markdown-it({html: false, linkify: false})`, sanitize links, replace
      the `<pre>`.
- [x] Tag server-side `<pre>` blocks for description/comments with
      `class="md"` in `todo_webui.py`.
- [x] Tests: static route (containment, 404, cache header), bootstrap
      reference present on show pages, `<pre class="md">` tags present.
- [x] Deferred TODO (single tracker issue): syntax highlighting for code
      fences and todo.txt/done.txt in the web UI (client-side) - filed as
      tracker issue 0a7d7e68.
