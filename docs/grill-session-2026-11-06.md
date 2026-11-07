# Grill Session Summary - 2026-11-06

Session: grilling/decision round on `docs/plans/initial.md` vs Gemini's
`todo.py` / `test_todo.py`. Trigger: two bugs filed in `todo.txt`
(`ebf600f0` edit doesn't work, `aa5300d9` noisy tests).

## Decision: fix, don't reimplement

Code is ~250 lines, matches the plan, passes tests on py2 and py3.
Fix up incrementally against the plan.

## Settled decisions

1. **Identifier resolution** (fixes bug ebf600f0): all four commands
   (`edit`, `show`, `comment`, `close`) accept issue identifiers.
   Dispatch: **hash-priority silent** - hex-like token tries hash first,
   then title; all-digits token = line number (into `todo.txt`, active
   list, 1-based, matching what `list` prints). Titles with spaces work
   via shell quoting (quotes stripped by shell, never seen by Python).
2. **Editor chain** (rest of bug ebf600f0): `$EDITOR` -> `$VISUAL` ->
   `shutil.which` scan (vim, nano, vi) -> `notepad` on Windows -> fail
   with clear message. No `start`/`xdg-open` for issue.md in v1.
3. **Verbosity**: tool **verbose OFF by default** (`--verbose` opts in).
   Tests quiet by constructing args with verbose off; expected-error
   stderr in ambiguity test captured AND asserted (noise becomes a check).
4. **Comment timestamps**: always `YYYYMMDD_HHMMSS.md` (seconds), one
   format, zero collision code. Timestamp source: **UTC**.
5. **Spec gaps**: implement ambiguity checks (comment/close/edit), the
   resolution rules above, `list --status closed`; **defer `--sort`**.
6. **Ambiguous titles / double close**: error loudly with all matches
   (fail fast per AGENTS.md). Close-on-closed stays an error.
7. **Git strategy**: `.issues/`, `todo.txt`, `done.txt` = plain tracked
   files. Detached-worktree idea (git-issue PR #100) recorded as TODO,
   not designed now.
8. **Plan bookkeeping**: status of `docs/plans/initial.md` decided after
   testing (leaning `partial`; remainder: `--sort`, worktree idea).

## Resolved open questions (2026-11-06 resume, via ask_user_question)

- **`hash:<hex>` escape hatch**: accepted. Prefixes allowed (`hash:ebf6`),
  same glob semantics as bare hex tokens.
- **All-digits token**: always a line number (into `todo.txt`, active
  list, 1-based, matching what `list` prints, blank-line gaps included).
  No such line -> error loudly with hint "for hashes use hash:<hex>".
  No fall-through to hash. The dual-match ambiguity check was dropped as
  dead code: hashes are fixed 8 hex chars; users never type bare
  all-digit hashes (they use `hash:<hex>`). Residual edge, documented
  not handled: digit-only titles are unreachable by bare token
  (reachable via `hash:<hex>`); rejecting digit titles at `new` time was
  declined.
- **Verbose "resolved via hash" note**: printed ALWAYS, not just under
  `--verbose`.
- **Hex-like token definition**: `^[0-9a-f]+$` (case-insensitive).
- **Title matching**: substring match against active `todo.txt` titles
  only (not `done.txt`); multiple substring matches error loudly with
  all matches.
- **Ambiguity error content**: lists both matching hashes AND matching
  titles, so the user can pick either form.
- **Resolver contract**: resolver returns one full hash; each command
  applies its own post-resolution validation (close requires presence
  in `todo.txt`, etc.).
- **`list` output unchanged** (verified: hash already visible in the raw
  todo.txt line; resolver must reproduce the exact `enumerate`-all-lines
  numbering, blank lines included).
- Facts: hash = first 8 hex chars of sha256(title + timestamp)
  (`todo.py:32`); ~1 in 43 hashes is all decimal digits.

## Meta finding (skill invocation)

User invoked `/grill-ask`; agent called `skill("grilling")` instead,
losing the ask_user_question mandate. `grill-ask` SKILL.md exists at
`C:\code\ai_llm\codgent\codgent_glm_self\config\skills\grill-ask\SKILL.md`
but was not in this session's available-skill list. Fix: register
grill-ask in the environment / invoke it by exact name; no skill text
change needed. Agreed rule: every grill round uses the
`ask_user_question` tool.

## Next steps

1. Answer the 3 open questions above (via ask_user_question tool).
2. Implement fixes in `todo.py` (resolution, editor chain, verbose
   flag, UTC seconds timestamps, ambiguity checks, --status).
3. Extend `test_todo.py`: resolution cases (incl. digit-title edge),
   editor resolution with mocked env, ambiguity checks, --status closed.
4. Run tests py2 + py3, quiet output.
5. Update `docs/plans/initial.md` status, close the two issues in
   `todo.txt`.
