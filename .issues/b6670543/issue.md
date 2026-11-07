Inconsistency introduced by ADR-0003 (hash subcommand, issue hash:47e35a1c).

`todo.py hash` and the close-time mint in `cmd_close` both mint via
`mint_hash_unique(title, taken)`: they retry (max 10, MINT_ATTEMPTS)
until the hash is unique across the hash: tokens of todo.txt AND
done.txt, then fail loudly. `cmd_add` still calls `generate_hash(title)`
directly, with no uniqueness check at all.

Why it matters: an 8-hex-char hash is 32 bits. A duplicate would
silently alias two issues (same .issues/<hash>/ directory, two lines
matching hash:<dup>, resolver returning an arbitrary one). The
timestamp makes it unlikely, not impossible, and the other two minting
paths now fail loudly where `add` would silently corrupt.

Fix sketch: in `cmd_add`, replace `generate_hash(args.title)` with
`mint_hash_unique(args.title, _all_hash_tokens())`. Note cmd_add
computes the hash BEFORE writing the todo.txt line, so `taken` must be
read first (it already is, by the call). `hash` and close stay as they
are.

Tests: extend test_todo.py with the same fake_generate stubbing used by
test_hash_collision_retries. No ADR needed; the decision is already
recorded in ADR-0003 Consequences.
