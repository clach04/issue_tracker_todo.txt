`list --sort` was specified in docs/plans/initial.md (--sort date|priority|hash) and deferred during the 2026-11-06 grill session, with no rationale recorded.

Real scope, settled in docs/plans/list-sort-and-priority-filter.md (grill session 2026-11-07):

- Purpose pinned first: the flag exists to find high-priority work and to find old work. Everything below follows from that.
- --sort date|priority only. --sort hash is DROPPED, not deferred: an 8-hex token has no ordering meaning, and file order already provides a stable arbitrary order.
- --reverse / -r added. -r alone reverses file order (one rule, no special case). Both flags apply to list --closed too - they are pure view flags.
- date key: first date token, after stripping the `x <completion-date>` prefix on archived lines. Lines with no date token sort last.
- priority key: (A)..(Z) in order, unprioritised last (a missing key is not "highest").
- Buckets (undated / unprioritised) stay last under --reverse: reversing orders the sortable block only.
- Every row keeps printing its TRUE Index line number in sorted output, so sorted numbers are visibly non-monotonic. This is the hard invariant: a number copied from any view addresses the same Index line for life.
- Stable tie-break on Index order.

Prerequisite shipped here: `add` appends instead of prepending (hash:6fdb5271), making Index line numbers stable for life. Sorted output would otherwise be unreadable.

Deferred out of this issue: `-s` short flag (hash:50000d8e); priority filtering for list --closed (hash:b8480e3f, blocked on the archive token-order bug).

Recorded as docs/adr/0004 (Index order vs display order). Close when the sort flags land.
