# AGENTS.md

ASCII-FIRST HARD RULE:
Use 7-bit ASCII for all agent-authored instructions, code comments, logs, and prose.

UTF-8 EXCEPTION:
Allow non-ASCII only when the file's data semantics require it
(e.g., person/place names, translations, fixtures, external-source text).
Do not alter existing non-ASCII data unless explicitly asked.

Write Python 3 and 2 compatible code using stdlib, if you need external libraries discuss, before using.

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

Plan files in `docs/plans/` carry a `Status:` line under their title
(missing = treated as `open`). A plan is done only when every TODO item
it spawned is closed or explicitly deferred to a named TODO item; done
plans move unchanged to `docs/plans/done/`. Session docs (grill
summaries, handover briefs) are exempt from the status scheme. Full
convention: `docs/plans/README.md`.

## Design records

- Glossary/terms -> CONTEXT.md (repo root). Vocabulary only, no
  implementation details.
- Settled decisions that are hard to reverse, surprising without context,
  or real trade-offs -> docs/adr/NNNN-slug.md (one short doc; scan
  docs/adr/ for the next number).
- When writing or editing either, prefer the domain-modeling skill
  (config/skills/domain-modeling/) - it carries the exact formats.
- Issue.md `Progress`/`Recommendations` notes are issue-scoped, not
  design records. A recommendation that settles a repo-wide decision
  with trade-offs should be promoted to docs/adr/NNNN-slug.md,
  referencing the issue hash; the issue.md note stays as the audit
  trail. See README.md for the decision table (record type vs
  question answered vs lifetime).

## Issue tracker filing (policy only; syntax lives in README.md)

- File deferred or observed work as tracker issues via
  `todo.py add '<title>' -d '<details>'` - including meta-tasks about the
  project itself (docs, process), not only code bugs.
- Always pass `-d`: never leave a stub issue.md. The body must contain
  enough for a stranger to act on it (what/why, repro or spawn source,
  references to plan/ADR/issue hashes).
- Tag issues with `--project` and `--context` where applicable.
- Resolve issues by identifier per docs/adr/0002; prefer the explicit
  `hash:<hex>` form in scripts and docs.
- Close what you finish. Fixing a tracked issue is not enough: the
  issue must be closed too (`todo.py close hash:<hex>`), or it
  lingers open in todo.txt forever.
- Track progress in issue.md. When working an issue in stages
  (e.g. "knock off the cheap ones"), append a `Progress (<date>):`
  section to `.issues/<hash>/issue.md` after each stage: what was
  done, what was found (including real bugs), what remains, and test
  counts. Never close an issue silently mid-work.
- Record recommendations and ideas in issue.md. Recommendations made
  during a session (design choices, trade-offs, effort estimates,
  "defer this" advice) belong in the issue's issue.md, not just in
  chat: they are lost otherwise. Attribute them to the agent that
  made them (e.g. "Codgent z-ai/glm-5.3-flash thinking: high").
  Use a `Recommendations (<date>):` section, separate from the
  `Progress (<date>):` section. Blank lines between entries; prefer
  short lines over long run-on paragraphs.
- Attribution wording. Attribute recommendations as
  "Codgent <model> (<date>)", using the model name from the coding
  harness when available. If the harness provides no model name,
  write "Codgent <model unknown>" and ask the user to supply it;
  never guess. The harness owns the model name; this is the agent's
  responsibility only when it already has it.
- Close with reasoning. Before closing, append to the issue's
  `.issues/<hash>/issue.md` a `Closed <date>: <reasoning>` footer
  (original content first, never edited in place; the reasoning goes
  after a blank line). The reasoning must state: what was decided
  (fixed / not-a-bug / deferred / duplicate), the evidence, and the
  hash of any issue spawned from the investigation. Never close an
  issue with a bare `todo.py close` and no issue.md footer.

Respond in English unless the user explicitly requests otherwise

Use python3 to invoke this project (not `py -3` and not `python`), if that fails use `py -3`.

Do NOT install packages or download anything from the network without
asking first. Ask per session, name the exact command/package list, and
wait for approval; the user often prefers to perform installs/network IO
themselves. Moving or unpacking already-downloaded files (e.g. into
tools/vendor/) is fine.
