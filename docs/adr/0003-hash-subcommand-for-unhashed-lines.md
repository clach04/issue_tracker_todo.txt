# `hash` subcommand for Unhashed Lines

The Index is a plain text file, so lines can be written by hand without
a `hash:` token. Those Unhashed Lines were previously only reachable by
`close` (which mints a hash at close time, ADR-0002). A batch repair
path was needed that does not make read-only commands write.

## Decision

`todo.py hash [identifier]` mints hashes for Unhashed Lines in
`todo.txt`:

- No argument: every Unhashed Line in the Index, in one pass.
- Argument: in-range line number, else case-insensitive title substring
  **restricted to Unhashed Lines**; ambiguity and targeting an already
  hashed line both fail loudly.
- The minted token is **appended at the end of the line**, not inserted
  in `add`'s canonical position.
- Minted hashes are retried until unique across the hash tokens of both
  `todo.txt` and `done.txt` (max 10 tries), then fail loudly.
- Idempotent: an already-hashed line is untouched; zero changes prints
  `nothing to mint` and does not write the file at all.

## Considered Options

- **Auto-backfill on every command**: rejected. Repairs happen by
  default, but `list`/`show` would silently rewrite a versioned file.
- **Lazy mint on first touch** (generalize the close exception to
  `show`/`comment`/`edit`): rejected. Every command grows a write path
  and line numbers shift under the user between the lookup and the
  action.
- **Insert the hash in canonical `add` position** (before `+project`
  /`@context`): rejected. `_title_from_line` cuts the title at the
  `hash:` token, so tags after the hash leave the derived title -
  existing tag-word title matches would silently stop resolving.
  Append-at-end changes no derived title.
- **No collision check** (what `add` does today): rejected for `hash`.
  A duplicate would silently alias two issues; the guard is three
  lines and failing loudly after 10 tries beats a corrupted index.
- **`--dry-run`**: dropped. `todo.txt` is versioned, so `git diff` is
  the preview; a preview flag is code nobody exercises.
- **Rewrite the Archive too**: deferred, not rejected - `done.txt`
  currently has no Unhashed Lines, and rewriting history as a side
  effect of a routine command is the riskiest write in the tool.

## Consequences

- `hash` and close-time minting are deliberately **stricter than
  `add`**: `add` still mints unchecked hashes. Tracked as its own issue; until then the two
  minting paths disagree on collision safety.
- Appending means a minted line's hash is not in the canonical
  position, so `add`-created and repaired lines look different. Text
  searching for `hash:` is the only property the tool relies on, so
  this is cosmetic - but it is visible in every repaired line.
- `close`'s no-hash exception stays. `hash` is optional: a repo that
  never runs it can still close hand-added lines.
- Minted hashes create no Details Directory; a repaired line remains
  title-only until a comment or `edit` bootstraps `.issues/<hash>/`.
