# ADR 0008: Web UI renders markdown client-side via vendored markdown-it

Status: accepted

Context: hash:e072da96. The read-only web UI (hash:51e9e387, ADR-0007) renders
`issue.md` and comment bodies as HTML-escaped plain text inside `<pre>` blocks.
The corpus (23 issue.md + 8 comment files, incl. imported real-world markdown)
uses bold (31 files), inline code (15), lists (9), headings (6), blockquotes
(6), fenced code (3), and inline links (1 file, 6 links, all http/https).
Reference-style links and images: zero occurrences.

## Decision

- **Render markdown client-side.** The server keeps sending the escaped
  `<pre>` blocks (v1 behavior, unchanged); a small bootstrap script reads each
  one, renders it with vendored markdown-it, and replaces the `<pre>` with the
  rendered HTML. No server-side rendering code, no Python markdown parser.
- **Library: markdown-it 14.1.0**, vendored at
  `tools/vendor/markdown-it-14.1.0.min.js` (123,618 bytes, MIT, jsdelivr).
  Chosen over marked.js because markdown-it has an `html: false` option
  built-in; marked.js v5+ removed it and needs a pre-escape hack that
  double-escapes entities inside code fences.
- **Options: `markdown-it({html: false, linkify: false})`.** All raw HTML
  tokens in the corpus (`<hash>`, `<date>`, `<title>`, `<pre>`, etc.) are
  data placeholders, not markup; they must render as escaped text, which
  `html: false` guarantees.
- **Link sanitization: http/https/mailto only.** Any other scheme
  (`javascript:`, `data:`, `vbscript:`, ...) renders as escaped plain text,
  not a link.
- **No-JS fallback = the escaped `<pre>`** (progressive enhancement). Server
  sends the same bytes it always did; JS is the upgrade path.
- **Delivery: `/static/<name>` route** in `todo_webui.py` with the same
  containment-check pattern as the attachments route; served from
  `tools/vendor/`. Cacheable, no page bloat.
- **Bootstrap lives as a static asset** (`/static/webui.js`), not inline in
  every page.

## Consequences

- No-JS users see the current v1 behavior (escaped `<pre>`), which is a
  correct, safe rendering of the content.
- The vendored asset is a pinned version, updated by replacing the file
  (versioned filename). Downloaded once, no runtime network dependency.
- Browser-side parsing is browser-dependent; the escaped `<pre>` fallback
  remains the ground truth for correctness.
- Code-fence syntax highlighting and todo.txt/done.txt highlighting are
  deferred to a separate tracker issue; they are also client-side.
