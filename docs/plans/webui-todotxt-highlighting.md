# Web UI todo.txt/done.txt highlighting (client-side custom grammar)

Status: done 2026-11-10 - todo.txt/done.txt grammar shipped, done.txt
listed under collapsed <details> on /; no-JS fallback unchanged.

Source: hash:0a7d7e68, part 2 (code-fence part done, ADR-0009). Decision:
highlight.js custom grammar for todo.txt/done.txt syntax, applied to the
list page (todo.txt) and a new done.txt listing section.

## Decisions

- Grammar: highlight.js sublanguage definition (no DOM, works on plain
  text), registered as `hljs.registerLanguage('todotxt', ...)`.
- Tokens: priority (A)/(B)/(C) traffic-light (A red, B orange, C yellow),
  completion date, `hash:` token (special color, distinct from generic
  key:value), generic `key:value` tags, `+project`, `@context`, bare
  URLs, and the `x` completion mark (done.txt).
- The list page (/) now loads webui.js (small, ~2.2KB) so the grammar
  applies there too.
- done.txt: new section on the / list page - a second table under a
  collapsed `<details>` element, highlighted with the same grammar.
- Highlighting is client-side only (ADR-0008/0009 pattern); server
  markup stays plain escaped text (no-JS fallback unchanged).

## TODO items

- [x] Add `todotxt` grammar to `webui.js` (highlight.js sublanguage).
- [x] Extend `/` list page: load webui.js, add done.txt section under
      collapsed `<details>` with line numbers.
- [x] Add token colors to `PAGE_STYLE` (traffic-light priorities, hash
      special color, key:value, project, context, date, URL).
- [x] Tests: done.txt section present on /; grammar applied to both
      tables; no-JS fallback unchanged (escaped text still present).
