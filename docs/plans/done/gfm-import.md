# GFM Task List Import (`md2todo.py`)

Status: done 2026-11-08 - `md2todo.py` shipped (separate tool, top-level only); deferred items filed as hash:68764906 (`--flatten`) and hash:8c1cad08 (second import mode).

Import a GitHub-Flavored Markdown file with task lists into the tracker.
New tool `md2todo.py` that imports `todo.py` as a library (not a
`todo.py` subcommand). One file per invocation.

Grill session 2026-11-07; all decisions below are settled.

## v1 mode: top-level only

Each top-level checklist item becomes one Issue. Nested children are
NOT tracked as Issues: they are stored verbatim in the parent's
`issue.md`. A `--flatten` flag (full recursive nesting: every checkbox
item becomes an Issue, child titles get the ancestor path prefixed,
e.g. `Draft the post / Crop the second one`) is reserved by name but
**fails loudly** in v1 with "not implemented yet". The name is locked
so a later version cannot be forced to use a different flag.

## Checklist line grammar

- List markers: `-`, `*`, `+`, and ordered (`N.` or `N)`, any number).
- Checkbox state: `- [ ]` unchecked, `- [x]` and `- [X]` checked
  (case-insensitive).
- Lines inside a fenced code block (``` ... ```) are NOT checklist
  items; they are content.
- Indented checkbox with no parent above it: treated as top-level
  (indentation is a hint, not a requirement; the file is malformed but
  the task is real).

## Content attribution

- Content BEFORE the first checklist item (headings, prose) -> the
  FIRST item's `issue.md`.
- Content between item A and item B -> B's `issue.md`, as preceding
  content (before B's nested block, no heading).
- Content inside a subtree (between a parent and its first child) ->
  part of the nested block, verbatim.
- Content at EOF (after the last item's subtree) -> the LAST item's
  `issue.md`, appended under a `## Notes` heading.
- Leading/trailing blank lines of any content region are trimmed;
  internal blank lines stay verbatim.

## issue.md assembly

`issue.md` is created ONLY when there is actual content (preceding
content, children, or trailing notes). A content-less item exists only
as its todo.txt / done.txt line.

Assembly:

```
# <title>

<originally: - [x]>          # only when checked-but-imports-open

<preceding content>

<nested block, dedented>
```

- Title header: `# <title>` (matches the existing `edit` bootstrap
  convention).
- Nested block: children with their indentation removed (dedented).
- `originally: - [x]` line: a checked parent whose subtree contains
  unchecked items imports as OPEN (see "State mapping"); its issue.md
  records the original checked state right after the title header.
- Overlong item (>200 chars) that ALSO has children: issue.md = `# ` +
  full title (no truncation), then the children block.
- Overlong item with NO children: issue.md = the full title as plain
  text, no header.

EOF trailing content is appended after the above, under `## Notes`.

## Overlong titles

Any title >200 chars is truncated in the Index line to 200 chars,
cut at a word boundary, with `...` (three ASCII dots, not Unicode)
appended. `issue.md` then carries the full title (see above).

- Hash is minted from the TRUNCATED title.
- Consequence: title-substring identifiers can only match the truncated
  text; the `hash:<hex>` form always resolves.

## State mapping

- `- [x]` / `- [X]` (and no unchecked descendants) -> imported as
  CLOSED: `x <today> <line> hash:<minted>` appended to `done.txt`,
  same format as `close`.
- `- [x]` parent with ANY unchecked descendant -> imported as OPEN in
  `todo.txt`; `issue.md` records `originally: - [x]` after the title
  header.
- `- [ ]` -> imported as OPEN in `todo.txt`.

## Index line format

Identical to `add`: `[priority?] [today] [title] hash:<h>` with today's
date, appended in file order (ADR-0004 chronological append). No
dedup check against existing issues (matches `add` behavior).

## Metadata: verbatim

No token extraction. The whole line after the checkbox is the title.
No `+project` / `@context` / `~duration` / `#type` / date extraction.
`md2todo.py` accepts global `-p` / `--project` / `--context` flags
applied to EVERY imported issue (same semantics as `add`).

## CLI

```
md2todo.py <file> [--dry-run] [-p A] [--project backend] [--context bug]
```

- Exactly one file argument.
- `--dry-run`: prints the per-issue plan (one line per issue:
  `would create (open) line N: <title>` / `would create (closed) ->
  done.txt`, plus would-create issue.md paths) and a summary, then
  the warning: hashes will differ on later runs (timestamp-based).
- `--flatten`: reserved, fails loudly ("not implemented yet").

## Errors (fail fast)

- Missing file: exit 1.
- Zero checklist items in the file: exit 1.

## Skipped content

- Empty checkbox item (`- [ ]` with no text):
  - with no children -> skipped with a warning summary line.
  - with children -> the item is skipped with a warning; its children
    are PROMOTED to top-level items and become Issues.
- Non-checklist content that is not attached to any item (there is no
  such case after the attribution rules above; all content is either
  attached to a preceding item or trailing at EOF).

## Hashing

Same `mint_hash_unique` / `generate_hash` path as `add` and the
close-time mint: uniqueness retry against all hashes in `todo.txt` and
`done.txt` (10 tries, then fail loudly). For overlong titles the hash
is minted from the truncated title.

## TODOs spawned by this plan

- [x] Implement `md2todo.py` (parser, content attribution, issue.md
  assembly, state mapping, index/done writing, dry-run).
- [x] Tests for `md2todo.py` in `test_todo.py` (stdlib, py2/py3).
- [x] README section for the import tool.
- [x] (Deferred) `--flatten` full recursive nesting mode - hash:68764906.
- [x] (Deferred) Second import mode: top-level-only via flag (`v1` is
  top-level only by default; revisit whether a flag is needed) -
  hash:8c1cad08.

## Implementation notes (resolved at build time)

- An overlong item with NO children would otherwise lose its full title
  (the Index line is truncated, and "issue.md = the full title as plain
  text" only spoke about overlong items that DO have children). It now
  always gets an `issue.md`: plain full title when childless, `# <full
  title>` + children block otherwise. Content-less SHORT items still get
  no `issue.md`.
- The budget for an overlong Index title is 200 chars of title, then
  `...` is appended (so the visible title can be 203 chars). A single
  long word with no space to cut at is hard-cut at 200.
- A skipped empty item (`- [ ]` with no text) is not Content: its own
  line never lands in a neighbouring issue's `preceding`/`## Notes`
  region. Inside a nested block the slice stays verbatim.
