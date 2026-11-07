# AGENTS.md

ASCII-FIRST HARD RULE:
Use 7-bit ASCII for all agent-authored instructions, code comments, logs, and prose.

UTF-8 EXCEPTION:
Allow non-ASCII only when the file's data semantics require it
(e.g., person/place names, translations, fixtures, external-source text).
Do not alter existing non-ASCII data unless explicitly asked.

Write Python 3 and 2 compatable code using stdlib, if you need external libaries discuss, before using.

Be ultra-concise and precise across all outputs. Prefer brevity over grammar.

If anything is unclear, ask a question before implementing.

Prefer assertions with descriptive messages over try/catch.
Use explicit type checks with no silent fallbacks; log actual vs expected types.
Add TODO comments only for unresolved assumptions that affect correctness.
Fail fast on unexpected input; log full technical context, but redact secrets.
Include stack trace plus semantic context (example: "Failed at model comparison step 2/5").
Use trace-level logs for major steps when debugging is enabled.

NEVER `git push` without explicit user confirmation, each and EVERY time.
NEVER `git commit` unless explicitly asked by the user.
NEVER use `git add -A` or `git add .`; always list files explicitly in `git add`.

## docs/plans status scheme

Every file in `docs/plans/` has a `Status:` line under its title:
`open` | `partial - <shipped, date>; remainder: <pointer>` (stays) |
`done <date>` (move the file to `docs/plans/done/`, unchanged). A plan is
done only when every TODO item it spawned is closed or explicitly deferred
to a named TODO item. Full convention: `docs/plans/README.md`.

## Design records

- Glossary/terms -> CONTEXT.md (repo root). Vocabulary only, no
  implementation details.
- Settled decisions that are hard to reverse, surprising without context,
  or real trade-offs -> docs/adr/NNNN-slug.md (one short doc; scan
  docs/adr/ for the next number).
- When writing or editing either, prefer the domain-modeling skill
  (config/skills/domain-modeling/) - it carries the exact formats.

Respond in English unless the user explicitly requests otherwise

Use python3 to invoke this project (not `py -3` and not `python`), if that fails use `py -3`.

Do NOT install packages or download anything from the network without
asking first. Ask per session, name the exact command/package list, and
wait for approval; the user often prefers to perform installs/network IO
themselves. Moving or unpacking already-downloaded files (e.g. into
tools/vendor/) is fine.
