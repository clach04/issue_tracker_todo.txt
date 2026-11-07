# docs/plans

Implementation plans and session handover briefs.

## Status scheme (convention)

Applies to **plan files** only. Line 2 of every plan (under the title) is
one of:

- `Status: open` - not started - if line missing, considered open.
- `Status: partial - <what shipped, date>; remainder: <pointer>` (stays here)
- `Status: done <date> - <1-line outcome>` (then move to `done/`)

Plans are 100% done only when every TODO item they spawned is closed or
explicitly deferred to a named TODO item. Move done plans unchanged into
`done/` (kept for the decision trail).

**Session docs** (grill summaries, handover briefs) are exempt from the
status scheme - no `Status:` line. Move a session doc into `done/` once
its decisions are distilled into ADRs and/or `CONTEXT.md`; it then sits
there as the decision trail behind those records.
