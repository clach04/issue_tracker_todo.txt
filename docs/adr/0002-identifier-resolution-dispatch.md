# Identifier Resolution Dispatch

Issue commands (`show`, `comment`, `close`, `edit`) accept one identifier
token that must resolve to exactly one Issue. Users have several natural
ways to name an issue (line number, hash prefix, title fragment, explicit
hash), so a single dispatch order governs them all.

## Decision

Dispatch order, tried in sequence:

1. **`hash:<hex>`** - explicit form, prefix allowed. Unambiguous by
   construction; always wins over any other interpretation.
2. **All-digits token** - an **Index line number** (1-based into
   `todo.txt`, matching exactly what `list` prints, blank lines
   included) **if the number is in range**. If the number is out of
   range (todo.txt stays small by design), the token is not a line
   number: fall through to the hash-prefix path, then title matching.
   (Refined 2026-11-07: the original rule errored loudly on out-of-range
   numbers with a `hash:<hex>` hint; the user's observation that line
   numbers only exist in a small list made the fall-through safe - a
   typo'd line number is always out of range, so no silent misrouting
   is possible.)
3. **Hex-like token** (`^[0-9a-fA-F]+$`, case-insensitive, not
   all-digits) - tries hash prefix first (hash: tokens in `todo.txt` /
   `done.txt` lines; the Details Directory is lazily created storage and
   may not exist), then title substring. When a hash matches, resolution
   ends and a "resolved via hash" note is printed **always** (not only
   under `--verbose`).
4. **Any other token** - case-insensitive substring match against
   **active** `todo.txt` titles only (not `done.txt`). Multiple matches
   error loudly listing all matches (both hashes and titles, so the user
   can pick either form).

The resolver returns one full hash; each command applies its own
post-resolution validation (e.g. `close` requires the Issue to be in
`todo.txt`; double-close stays an error).

## Considered Options

- **Length split** (digits < 5 = line number, 5+ = hash): rejected.
  Hashes are fixed 8 hex chars, so 5-6 digit tokens can still be hash
  *prefixes*; the split would misread long line numbers in large lists.
- **Fall through to hash on missing line number**: originally rejected
  ("I typo'd line 999" would silently resolve to hash `999a...`), then
  accepted 2026-11-07 in a refined form: out-of-range *all-digit* tokens
  fall through. The original concern was unfounded because a typo'd line
  number is always out of range (todo.txt stays small), so the
  fall-through is safe by construction.
- **Dual-match ambiguity check** (all-digits token matching both a line
  and a hash prefix): dropped as dead code. Users never type bare
  all-digit hashes; the explicit `hash:` form covers that case.
- **Drop hash prefixes entirely** (full 8-char hashes only): rejected;
  short prefixes are the convenient copy-paste workflow.

## Consequences

- **Residual edge, resolved**: a digit-only title (e.g. "12345") is
  reachable by bare token when the number is out of range (fall-through
  to hash then title), and always via `hash:<hex>`.
- ~1 in 43 hashes is all decimal digits (8 hex chars); this is invisible
  under the bare-token rule because those hashes are only ever addressed
  via `hash:<hex>`.
- `list` numbering must stay byte-compatible with the resolver's
  line-number path (including blank-line gaps).
