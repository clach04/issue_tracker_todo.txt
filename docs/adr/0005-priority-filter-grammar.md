# Priority Filter Grammar

`list -p` filtered by **substring**: it kept a line when the literal
`(<letter>)` appeared anywhere in it. That is exact-match only, so
"show me everything at A-or-better" - the actual reason to filter -
required running the command once per letter and reading three lists.
`-p` was also the only way to express priority at all, so a typo like
`-p ABC` was silently *not* rejected: it matched nothing and printed an
empty list, which reads as "no matching issues".

## Decision

`list -p` / `--priority-filter <spec>` parses a grammar instead of a
substring. `A` is highest, `Z` lowest.

| Shape | Meaning | Example |
| --- | --- | --- |
| `C` | exact | only `(C)` |
| `A-C` | range, inclusive | `(A)`, `(B)`, `(C)` |
| `C+` | C **and better** | `(A)`..`(C)` |
| `C-` | C **and worse** | `(C)`..`(Z)` |

- Case-insensitive, surrounding whitespace trimmed.
- The bound forms take **any** letter, including a range end: `A-` is
  A and worse (A..Z, i.e. every prioritised issue) and `Z+` is its
  mirror. No nonsense-value exception: one grammar, applied literally.
- Everything else **fails loudly** (exit 1) naming the accepted shapes:
  `ABC`, `-C`, `A-Z-`.
- A **swapped range** (`C-A`) also fails loudly; it is not silently
  swapped. A silent swap makes the typo untestable, and the empty result
  after a bad guess reads as "no matching issues".
- Unprioritised lines never match: a spec orders priorities, and a
  missing key is not a priority (ADR-0004). `A-Z` is therefore the
  "prioritised only" filter.
- The long flag renames `--priority` -> `--priority-filter`; `-p` stays.
  `add` keeps `-p` / `--priority`: `add` *sets* a priority, `list`
  *filters* by one - different verbs, so different names.
- **Open list only.** `list --closed` keeps today's `-p` behaviour
  verbatim - a literal `(C)` substring test on the archived line - and is
  documented as legacy, because archived-line priority is not reliably
  parseable yet (hash:b8480e3f). A spec that needs the grammar on that
  path fails loudly rather than printing an empty list.
- `--help` carries one line (`Filter: A, A-C, C+, C-`); the full table
  and the error contract live in README.

## Considered Options

- **`+C` / `-C` as the better/worse markers**: rejected. `-C` collides
  visually with `-p`-style option syntax and with a range's `A-C` dash;
  the postfix form (`C+`, `C-`) keeps the letter next to `-p`'s
  argument.
- **`A..C` (two dots) for the range**: rejected. `A-C` is what a todo.txt
  user types, and the grammar already rejects `A-Z-` loudly, so there is
  no ambiguity to resolve with extra punctuation.
- **Word forms** (`high`, `low`, `better-than-C`): rejected. No natural,
  non-arbitrary mapping from words onto a single letter.
- **Silently swap a reversed range**: rejected (see above).
- **Silently ignore an unparsable spec**: rejected - prints an empty
  list, which is indistinguishable from a real empty result.
- **Full grammar on `list --closed`**: deferred, not rejected - blocked
  on the archive token-order bug (hash:b8480e3f). Until then, a
  non-exact spec on `--closed` fails loudly.
- **Keep `--priority` as the long name**: rejected. It reads like the
  *value* setter that `add` has; the filter takes a *spec*.

## Consequences

- `list -p A-C` (and the other three shapes) becomes the one-liner that
  answers "what is most urgent", which `--sort priority` then orders.
- `-p ABC`, `-p A-Z-`, and `-p C-A` are now errors, not empty lists. Any
  script relying on the old silent-substring behaviour breaks loudly.
- Specs whose first character is `-` need the attached form
  (`--priority-filter=-C`): `-p -C` is eaten by the option parser
  (argparse exits 2) before the grammar ever sees it.
- `list --closed -p <exact letter>` keeps working unchanged; the
  substring accident (`"(C)" in line`) stays exactly as it is today, so
  archived-line filtering is bit-for-bit the behaviour that shipped. It
  becomes an explicit exact-match test only when hash:b8480e3f is fixed.
