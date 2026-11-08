# GFM Task List Import: Separate Tool, Flat Model

Users write GFM task lists (checklists, often nested) in GitHub files
and want them imported into the tracker. The Index (`todo.txt`) is one
flat line per Issue, so nesting cannot be represented in the data model.
The decisions below were settled in a grill session (2026-11-07,
`docs/plans/gfm-import.md`).

## Decision

**Import lives in `md2todo.py`, a separate tool that imports `todo.py`
as a library** - not a `todo.py` subcommand. Import is a one-shot
conversion, not a tracker operation; keeping it out of `todo.py` keeps
the tracker's CLI surface small. Consequence: the tool must reuse the
tracker's minting/appending functions rather than reimplement them.

**v1 imports top-level items only; nested children are stored verbatim
(dedented) in the parent's `issue.md`, not as Issues.** The Index stays
flat. A `--flatten` flag (every checkbox item at any depth becomes an
Issue) is reserved by name but fails loudly in v1; the name is locked so
a later version is not forced to rename it.

**Checked items import as closed, except a checked parent with any
unchecked descendant imports as open** (its `issue.md` records
`originally: - [x]`). This mirrors the whole point of a checklist: an
item with open children is not done.

**Titles over 200 chars are truncated in the Index line to 200 chars at
a word boundary with `...` appended; the hash is minted from the
truncated title.** `todo.txt` stays grep-friendly. Consequence: a
title-substring identifier can only match the truncated text; the
`hash:<hex>` form always resolves. The full title is preserved in
`issue.md`.

## Amendment 2026-11-08b: verbatim block in issue.md

Imported issue.md now leads with the item's ORIGINAL source lines - the
`- [x]` checkbox line itself plus its subtree, exactly as authored,
indentation intact, never dedented. The previous model stripped the
checkbox line and dedented the rest under a `# <title>` header; reading
the result next to the source was hard, and the headerless overlong
special case made files look corrupt. Title/bullet duplication is
accepted: the block's first line IS the title. A bare item (no subtree,
no content) still gets no issue.md - a pure duplicate of the Index line
is not content. When the issue has other content (preceding prose,
notes) but its subtree is empty, the checkbox line still leads so every
issue.md opens with the item itself.

## Amendment 2026-11-08c: deterministic title-only hashes

Import hashes derive from the (truncated) title ALONE - sha256 of the
title, no timestamp. Re-importing after cleanup reproduces identical
hashes, so an import can be debugged by edit/revert/re-run instead of
hand-editing todo.txt. Consequences:

- Re-importing unchanged content into a populated tracker fails loudly
  ("already in the tracker as hash:<hex>") instead of silently minting
  a different hash - silent re-minting would defeat reproducibility.
- Duplicates within one file retry deterministically
  (`sha256(title + " #N")`), same retry budget as todo.py's mints.
- todo.py's `add` / `hash` / close-time mints stay timestamp-based:
  interactive mints SHOULD differ for identical titles.

## Amendment 2026-11-08: continuation-line attribution

The original attribution rules (above) defined an item's subtree by
checkbox nesting only. A non-checkbox line indented under an item - a
"Done (date): ..." note, a plain prose continuation - was invisible to
the subtree boundary, so it fell into the NEXT item's preceding content.
Real consequence (2026-11-08 real_test import): a done note ended up in
the wrong `.issues/<hash>/issue.md`, and a headerless overlong-title
body made the file look corrupt.

**Amended rule: a non-checkbox, non-fenced line continues the nearest
preceding item when it is indented deeper than that item's own indent.**
Fenced content and blank lines inside a continuation run continue the
item too. Outdented (unindented) prose between two items is unchanged:
it stays the NEXT item's preceding content, matching the original
attribution. Consequence: a checked item with a Done note now imports
closed AND contentful (its notes live in its own issue.md) - the whole
point of a Done note is that it documents that item.

## Considered Options

- **Subcommand `todo.py import gfm <file>`**: rejected; import is a
  conversion tool, not an issue operation, and a separate script keeps
  `todo.py` small.
- **Every checkbox item becomes an Issue** (full nesting): rejected for
  v1 - the tracker has no parent/child model, and flattening with
  ancestor-path prefixes changes the schema of every title. Deferred to
  a reserved `--flatten` mode, not rejected.
- **Only top-level items become Issues; nested children dropped**:
  rejected - children are real work and must not be silently lost.
- **Completed `- [x]` items imported as open**: rejected; state maps
  1:1 onto Open/Archive, and the parent-with-open-children rule covers
  the only real exception.
- **Hash from the full title**: rejected; the hash is derived from the
  title as it appears in the Index, so Index and Archive stay
  self-consistent and the hash is reproducible from the visible line.
- **Extract `+project`/`@context`/`~duration`/`#type` tokens from item
  text**: rejected - GFM files use `@mentions` as mentions, not
  contexts; titles are imported verbatim.
- **No `--dry-run`** (consistent with `hash`'s "git diff is the
  preview"): rejected; an import creates many `.issues/` directories and
  many Index lines at once, and `git checkout .` is a blunt undo. The
  dry-run must print the "hashes will differ on later runs" warning.
