# Identifier Resolution Dispatch

Issue commands (`show`, `comment`, `close`, `edit`) accept one identifier
token that must resolve to exactly one Issue. Users have several natural
ways to name an issue (line number, hash prefix, title fragment, explicit
hash), so a single dispatch order governs them all.

## Decision

Dispatch order, tried in sequence:

1. **`hash:<hex>`** - explicit form, prefix allowed. Unambiguous by
   construction; always wins over any other interpretation.
2. **All-digits token** - always an **Index line number** (1-based into
   `todo.txt`, matching exactly what `list` prints, blank lines
   included). If the line does not exist: error loudly with a
   `hash:<hex>` hint. **Never falls through to hash lookup.**
3. **Hex-like token** (`^[0-9a-fA-F]+$`, case-insensitive, not
   all-digits) - tries hash prefix first (glob in Details Directory),
   then title substring. When a hash matches, resolution ends and a
   "resolved via hash" note is printed **always** (not only under
   `--verbose`).
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
- **Fall through to hash on missing line number**: rejected. "I typo'd
  line 999" would silently resolve to hash `999a...`. Fail fast instead.
- **Dual-match ambiguity check** (all-digits token matching both a line
  and a hash prefix): dropped as dead code. Users never type bare
  all-digit hashes; the explicit `hash:` form covers that case.
- **Drop hash prefixes entirely** (full 8-char hashes only): rejected;
  short prefixes are the convenient copy-paste workflow.

## Consequences

- **Residual edge, accepted**: a digit-only title (e.g. "12345") is
  unreachable by bare token; it resolves only via `hash:<hex>`.
  Rejecting digit-only titles at creation time was declined.
- ~1 in 43 hashes is all decimal digits (8 hex chars); this is invisible
  under the bare-token rule because those hashes are only ever addressed
  via `hash:<hex>`.
- `list` numbering must stay byte-compatible with the resolver's
  line-number path (including blank-line gaps).
