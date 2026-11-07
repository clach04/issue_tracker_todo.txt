Deferred from ADR-0003 / docs/plans/mint-no-hash-lines.md.

`todo.py hash` repairs todo.txt only. done.txt (the Archive) has no mint path, so a hand-written line that ends up in done.txt - e.g. pasted by hand, or a repo that used the tracker before close-time minting existed - can never acquire a hash, and is therefore unreachable: identifiers resolve against todo.txt only, and the Archive is reachable via hash.

Current state: done.txt has zero Unhashed Lines (checked 2026-11-07), so this is speculative, not broken.

Design sketch if wanted: `todo.py hash --closed` (or `--archive`) reuses cmd_hash with filepath = DONE_FILE. Open questions to settle first: (a) is rewriting the Archive as part of a routine command acceptable, given it is the most dangerous write in the tool; (b) should the appended token go after `x <date> <date> <title>` with the same append-at-end rule (title derivation strips the leading x/date so it stays consistent); (c) does the existing todo.txt retry guard need to be told about archive-only hashes (it already reads both files - just verify).