# Index Order vs Display Order

`todo.txt` had no stated ordering contract, and `list` printed the file
in file order. The POC's `add` wrote the new line at the **top**, so
every `add` renumbered the whole Index; a line number copied from `list`
silently addressed a different Issue after the next `add`. Line numbers
are the cheapest Identifier (ADR-0002), and their whole value is
stability. Separately, the deferred `--sort` flag (hash:8d8ab446) needed
a rule for what "sorted" means when the file itself also has an order.

## Decision

**Index order** = the physical line order of `todo.txt`, which is
**chronological**:

- `add` **appends**, matching `close` -> `done.txt`, which has always
  appended. Prepend was inherited from the POC, never argued, never
  documented.
- **`add` appends, so it never renumbers.** An Index line number is
  stable only while the issue stays open: `close` removes its line and
  shifts every later line number up, and hand edits to `todo.txt` can
  renumber too. For a reference that survives closing and renumbering,
  copy the `hash:<hex>` identifier instead. (Amended 2026-11-08: the
  original claim that line numbers were "stable for life" was wrong -
  see Consequences.)
- `add` prints `Created issue [<hash>] at line N: '<title>'` - only
  honest because append made N stable against `add`.

**Display order** = what `list` prints, which is Index order unless a
view flag overrides it:

- `--sort date|priority` and `--reverse`/`-r` reorder the **display
  only**; the file is never rewritten.
- Every printed row keeps its **true Index line number**, so sorted
  output is visibly non-monotonic (`7`, `2`, `11`). This is the
  invariant, restated: the number means the Index line, never the row
  position on screen.
- Tie-break is Index order (stable sort), so output is deterministic.
- `--reverse` without `--sort` reverses file order. One rule, no special
  case; on a pre-append file it yields "oldest first".

**Sort keys:**

- `date` - the first date token of the line; for an archived line, the
  first date token *after stripping the* `x <completion-date>` *prefix*.
  Lines with no date token sort **last**.
- `priority` - `(A)`..`(Z)` in order, then unprioritised **last**. A
  missing key is not "highest".
- **Buckets stay last under `--reverse`**: reversing orders the sortable
  block only, so `--sort priority -r` still shows prioritised work first
  and the junk drawer stays out of the way.

`--sort`/`-r` apply to `list --closed` too: they are pure view flags.

## Considered Options

- **Keep prepending** (status quo): rejected. It renumbers every Issue
  on every `add`, which makes remembered line numbers worthless and
  makes any sorted view's numbers churn. Nothing depended on order.
- **Prepend, but print nothing about line numbers**: rejected. The
  number would stay unknowable at add time while remaining the cheapest
  Identifier; printing it is one format string.
- **`--sort hash`**: **dropped**, not deferred (originally specified in
  `docs/plans/done/initial.md`). An 8-hex token has no ordering meaning;
  a stable arbitrary order is exactly what file order already provides.
- **Sort by rewriting `todo.txt`** (make display order persistent):
  rejected. Sorting is a view concern; a versioned file should change
  only when content changes, and rewriting would renumber nothing but
  would bury real edits in a `git diff` full of moved lines.
- **Renumber displayed rows in sorted output** (`1..N`): rejected - it
  produces numbers that address nothing and would silently misroute
  every subsequent command.
- **Bucket-last exceptions under `--reverse`** (flip everything,
  including empties to the top): rejected. Dated/prioritised work is the
  reason the flag exists; putting the junk drawer first under `-r`
  defeats it.

## Consequences

- Existing repositories keep their current (reverse-chronological)
  `todo.txt` until new Issues append below; there is no migration and
  none is needed, since nothing depended on prepend.
- `-s` for `--sort` is deferred (hash:50000d8e), not rejected - it
  collides conceptually with the POC's `--status` and earns its place
  only after real use.
- Sorting the Archive exposes a pre-existing format bug: archived lines
  put `(P)` after `x <completion-date>`, and `_title_from_line` never
  strips the `x <date>` prefix (hash:b8480e3f). Date sort must strip the
  prefix itself; priority filtering on `--closed` stays exact-match
  until that issue is fixed.
- **Amended 2026-11-08 (hash:b8e9d849)**: the original Decision claimed
  "Line numbers are stable for life" and called it the hard invariant of
  this change. That was wrong: `close` removes a line and shifts every
  later line number up, and hand edits to `todo.txt` can renumber too.
  The invariant that survives is the append order itself: `add` never
  renumbers an existing line. For anything copied down long-term, use
  the `hash:<hex>` Identifier (ADR-0002), not the line number.
