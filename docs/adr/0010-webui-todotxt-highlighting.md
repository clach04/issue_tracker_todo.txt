# ADR 0010: Web UI todo.txt/done.txt highlighting via highlight.js custom grammar

Status: accepted

Context: hash:0a7d7e68, part 2. The web UI list page renders todo.txt
lines as plain text (with a link to the show page). The user wants
syntax highlighting for todo.txt/done.txt tokens: priority (A)/(B)/(C),
completion date, hash: token, +project, @context, bare URLs, and the
x completion mark (done.txt). Generic key:value tokens should also be
highlighted, with hash: as a special case (different color).

Decision: highlight.js custom grammar (sublanguage), registered as
`hljs.registerLanguage('todotxt', ...)`, applied client-side. The list
page now loads webui.js (~2.2KB) so the grammar applies there. done.txt
is listed on the / page under a collapsed <details> element, with the
same grammar. Priorities are traffic-light (A red, B orange, C yellow).

Alternatives:
- Server-side regex highlighting: adds server-side complexity, breaks
  the no-JS = plain text invariant (ADR-0008/0009 pattern).
- CSS-only: no tokenizer, no per-token classes.

Consequences:
- webui.js grows (~2.2KB -> ~5KB); still first-party, no new vendor
  asset.
- The list page now loads scripts (previously only show pages did).
- done.txt is now visible on the / page (collapsed); the no-JS fallback
  shows the same escaped text.
- A future done.txt-specific page (if any) reuses the same grammar.
