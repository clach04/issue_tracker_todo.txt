# Mint hashes for Unhashed Lines

Status: done 2026-11-07 - `todo.py hash` shipped; deferred items filed as hash:b6670543 (add retry) and hash:b6e88862 (done.txt backfill).

Add a `hash` subcommand that bestows a hash on Unhashed Lines in the
Index, so a hand-written `todo.txt` line stops being a second-class
citizen. Grill session 2026-11-07; decisions below are settled.

Spawned from todo.txt item `new mode to add hashes for entries missing
a hash entry` (hash:47e35a1c).

## Decisions

1. **Entry point**: new subcommand `todo.py hash [identifier]`. Never
   automatic on other commands (`list` must stay side-effect free).
   Prose uses the glossary verb *Mint*; the CLI name is `hash`.
2. **Scope**: `todo.txt` only. `done.txt` backfill deferred (issue
   filed from this plan).
3. **No argument** - whole Index, every Unhashed Line. **With an
   argument** - in-range line number first, else case-insensitive title
   substring **restricted to Unhashed Lines** (a hashed match is not a
   candidate). Multiple unhashed matches -> loud ambiguity error.
4. **Placement**: append ` hash:<hex>` at the end of the line. Keeps
   the derived title unchanged (tags stay inside the title, unlike
   `add`), so existing title-substring identifiers keep working.
5. **Idempotent**: already-hashed lines are untouched. Zero changes
   prints `nothing to mint` and exits 0 **without writing**, so no
   mtime churn and no EOL normalization.
6. **Targeted on a hashed line** -> loud error, exit 1 (Q10 overridden
   on purpose: `hash <n>` naming a hashed line is a user mistake, not a
   no-op).
7. **Collision guard**: minted hashes are retried until unique against
   the hash tokens of both `todo.txt` and `done.txt`, max 10 tries,
   then fail loudly.
8. **No `--dry-run`**: `git diff` is the preview; `hash` prints one
   line per minted entry as the audit trail.
9. **No Details Directory** creation: title-only laziness (ADR-0001)
   holds; `.issues/<hash>/` still appears on first comment or edit.
10. **`close`'s no-hash mint exception stays** (ADR-0002 unchanged).
    `hash` is the proactive path, `close` the reactive one; both share
    `generate_hash` plus the retry guard.

## Work

- [x] `docs/adr/0003-hash-subcommand-for-unhashed-lines.md`.
- [x] `CONTEXT.md`: terms *Unhashed Line* and *Mint*.
- [x] `README.md`: `hash` subcommand section.
- [x] `todo.py`: `mint_hash_unique`, `_unhashed_lines`, `cmd_hash`,
      subparser wiring; `cmd_close` reuses the retry guard.
- [x] `test_todo.py`: whole-file mint (CRLF + blank lines + existing
      hashes preserved), idempotent rerun, targeted line/title,
      targeted hashed error, forced collision retry.
- [x] Dogfood: run `todo.py hash` on this repo's 6 Unhashed Lines
      (lines 5-10, including this item), review the diff.
- [x] File deferred issues: `add` lacks the uniqueness retry
      (hash:b6670543); `done.txt` has no backfill path (hash:b6e88862).

## Deferred

- `hash --closed` for `done.txt` - hash:b6e88862.
- Collision guard for `add` - hash:b6670543; `hash` and close-time
  mint are deliberately stricter than `add` until fixed.
