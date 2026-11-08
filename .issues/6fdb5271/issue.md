`cmd_add` writes the new line at the TOP of todo.txt (new_line + content), so every `add` renumbers every existing issue. A line number copied from `list` silently points at a different issue after the next add.

Why it matters: an Index line number is the cheapest Identifier (ADR-0002) and its value is stability. Prepend was inherited from the POC: never argued, never documented.

Fix: append instead, matching `close` -> done.txt (which appends). Settled in docs/plans/list-sort-and-priority-filter.md decision 1, recorded in docs/adr/0004 (index vs display order). The same commit makes `add` print the new line number ("Created issue [<hash>] at line N"), honest only once append makes the number stable.