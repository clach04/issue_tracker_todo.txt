# Index order, `list --sort`, and the priority filter

Status: open - settled by a grill session 2026-11-07; not started.

Spawn sources: tracker issue hash:8d8ab446 (`--sort`, deferred from
`docs/plans/done/initial.md`), plus two items filed by this session
(append-instead-of-prepend change; `-s` short flag).

The issue that started this (`--sort`) carried no rationale, so the
session first pinned what the flag is *for*: finding high-priority work
and finding old work. Everything below follows from that.

## Decisions

### Ordering (-> ADR-0004)

1. **`add` appends** to `todo.txt` instead of prepending. Index order
   is chronological, matching `close` -> `done.txt` (which appends).
   Prepend was inherited from the POC, never argued, never documented;
   it renumbered every issue on every add, which silently invalidated
   any remembered line number.
2. **Line numbers are stable for life.** A number copied from any view
   addresses the same Index line; sorted output prints each row's true
   index line number, so sorted numbers are visibly non-monotonic. This
   is the hard invariant of the change, not a side effect.
3. `add` prints the new line number: `Created issue [<hash>] at line N`
   - only honest once append made it stable.
4. **`--sort date|priority`**, plus **`--reverse` / `-r`**. No `-s`
   (TODO filed: revisit after real use).
5. **`--sort hash` is dropped** from the original spec. An 8-hex token
   has no ordering meaning; a stable arbitrary order is what file order
   already provides.
6. **`--reverse` without `--sort`** reverses file order. One rule, no
   special case, and it gives "oldest first" on a pre-append file.
7. **`--sort` / `-r` apply to `list --closed` too** - they are pure
   view flags.
8. **`date` key**: open line -> first date token. Archived line ->
   first date token after stripping `x <completion-date>`. Lines with
   no date token sort **last**.
9. **`priority` key**: `(A)`..`(Z)` in order, then unprioritised
   **last**. A missing key is not "highest".
10. **Buckets stay last under `--reverse`**: reversing orders the
    sortable block only, so `--sort priority -r` still shows prioritised
    work first and the junk drawer stays out of the way. (Corollary of
    8/9, stated in the ADR so it needs no separate decision.)

### Priority filter (-> ADR-0005)

11. `list -p/--priority-filter <spec>` with grammar `C` (exact),
    `A-C` (range), `C+` (C **and better**, i.e. A..C), `C-` (C **and
    worse**, i.e. C..Z). A is highest.
12. Case-insensitive, surrounding whitespace trimmed.
13. Everything else (`ABC`, `A-`, `-C`, `A-Z-`) **fails loudly** with
    the accepted shapes. A swapped range (`C-A`) also fails loudly
    rather than being silently swapped: a silent swap makes the typo
    untestable, and an empty result reads as "no matching issues".
14. `list`'s long flag renames `--priority` -> `--priority-filter`;
    `-p` is kept. `add` keeps `-p/--priority` (it *sets*; the verbs
    differ, so the names differ).
15. Open list only. `list --closed` keeps today's exact-match `-p`,
    because archived-line priority is currently unparsable (see the
    issue filed below).
16. `--help` gets one line (`Filter: A, A-C, C+, C-`); the full table
    and the error contract live in README.

## Work

Three commits, each pairing an ADR with the code it describes.

- [ ] File tracker items first, so the spawn trail exists:
      - append change (`add` prepends) - its own issue;
      - archived lines deviate from todo.txt token order: `(P)` sits
        after `x <completion-date>`, `_title_from_line` never strips
        the `x <date>` prefix so archived titles are unaddressable,
        and only 4/13 archived lines carry a priority token (could be
        split into "parse bug" and "`--closed` filter gap");
      - TODO: `-s` short flag for `--sort`, revisit after real use;
      - update hash:8d8ab446's body to this plan's real scope.
- [ ] Commit 1: `docs/adr/0004-*.md` (index vs display order), append
      in `cmd_add`, `at line N` output, tests ("add does not renumber
      existing issues"), README ordering contract.
- [ ] Commit 2: `--sort date|priority`, `--reverse`/`-r`, both files,
      stable tie-break on index order, buckets last under reverse,
      README (incl. the undated-lines caveat for date sort).
- [ ] Commit 3: `docs/adr/0005-*.md` (grammar, with `+C`/`-C`,
      `A..C` and word forms recorded as rejected), `--priority-filter`
      parser + rename, README grammar table, help line, tests for every
      accepted shape and every rejected one.
- [ ] Close hash:8d8ab446 and the two filed issues once their commits
      land.

## Deferred

- `-s` for `--sort` (TODO filed this session).
- Priority filtering for `list --closed` (blocked on the archive-format
  issue).
- Any `--sort hash`; the key is dropped, not deferred.

## Testing notes

- Append: existing issues keep their numbers across an `add` (assert
  the pre-add number still resolves to the same hash).
- Sort: both keys, both directions, both files, buckets last,
  tie-break = index order, `-r` alone = reversed file order.
- Filter: `C`, `A-C`, `C+`, `C-`, lowercase, padded, plus each rejected
  form exiting 1 with the accepted shapes in the message.
- Keep the suite quiet (stdout/stderr captured as today).
