# Local Issue Tracker (`todo.py`)

A lightweight, local-first issue and bug tracking system for repositories that combines the simplicity of `todo.txt` with rich flat-file descriptions, timestamped comments, and attachments.

Designed for developers who want a fast, grep-friendly, dependency-free tracker living directly inside their git repository.

---

## Features

  - **Standard Library Only**: Written in pure Python, compatible with both **Python 2 (2.7+)** and **Python 3**. No external dependencies required!
  - **`todo.txt` Compatible Index**: Open tasks live in a human-readable `todo.txt` file at your repo root, extended with clean custom metadata (`hash:ABC12345`).
  - **Automatic Archiving**: Closed issues migrate automatically from `todo.txt` to `done.txt`, keeping your active view clean and lightweight.
  - **Rich Flat-File Details**: Issues with a description get a sibling `.issues/<hash>/` directory:
    - `issue.md`: The primary issue body/description.
    - `comments/`: Chronological comment markdown files named with UTC timestamps (`YYYYMMDD_HHMMSS.md`). Created on first comment.
    - `attachments/`: A dedicated folder for screenshots, logs, or associated files.

    Title-only issues (added without `-d`) live in `todo.txt` alone until their first comment or `edit`, which lazily creates the directory.

    Manually added `todo.txt` lines without a `hash:` token are supported
    for closing: `todo.py close <line number>` mints a hash at close time
    and archives the line with it (`x <date> <line> hash:<minted>`).

---

## Index order

`todo.txt` is **chronological**: `add` appends, exactly as `close`
appends to `done.txt` (ADR-0004).

- **Line numbers are stable for life.** A number copied from any `list`
  output addresses the same Index line forever; a later `add` never
  renumbers an existing issue.
- `add` prints the new number:
  `Created issue [<hash>] at line N: '<title>'`.
- A `todo.txt` written before this change is reverse-chronological (the
  old `add` prepended). No migration is needed: `--reverse` reads such a
  file oldest-first, and new issues simply append below the old ones.
- Display order may differ from Index order once `--sort` or
  `--reverse` are used, but every printed row keeps its **true Index
  line number**, so sorted output is visibly non-monotonic. The number
  always means "the Index line", never "the row on screen".

## Filtering by priority

`list -p` / `--priority-filter` takes a **spec**, not a letter lookup
(ADR-0005). `A` is highest, `Z` lowest.

| Spec | Meaning | Matches |
| --- | --- | --- |
| `C` | exact | `(C)` only |
| `A-C` | range, inclusive | `(A)`, `(B)`, `(C)` |
| `C+` | C **and better** | `(A)`..`(C)` |
| `C-` | C **and worse** | `(C)`..`(Z)` |

```text
todo.py list -p A-C          # A through C
todo.py list -p B+           # B and better (A, B) - the "do this next" list
todo.py list -p B+ --sort priority
```

- Case-insensitive; surrounding whitespace is trimmed.
- The bound forms take any letter: `A-` is every prioritised issue,
  `Z+` its mirror. `A-Z` is the "prioritised only" filter.
- **Unprioritised issues never match** a spec: a missing priority is not
  a priority, and `--sort priority` puts them last.
- Rejected loudly (exit 1) with the accepted shapes in the message:
  `ABC`, `-C`, `A-Z-`, and a **swapped range** like `C-A` (never
  silently swapped - an empty list after a bad guess reads as "no
  matching issues"). A spec starting with `-` needs the attached form,
  `--priority-filter=-C`, because `-p -C` is swallowed by the option
  parser.
- `list --closed` accepts an **exact letter only** (`-p C`). Archived
  lines are not reliably parseable for priority yet (hash:b8480e3f), so
  any grammar spec on `--closed` fails loudly rather than printing an
  empty list.
- `add` keeps `-p` / `--priority`: it *sets* a priority, `list`
  *filters* by one.

## Sorting the list

`--sort` and `--reverse`/`-r` reorder the **display only**; the Index
file is never rewritten (ADR-0004).

```text
todo.py list                       # Index order (chronological)
todo.py list --sort priority       # (A)..(Z) first, unprioritised last
todo.py list --sort date           # oldest first
todo.py list --sort date -r        # newest first
todo.py list -r                    # reversed Index order
todo.py list --closed --sort date  # view flags apply to the Archive too
```

- Every row keeps its **true Index line number**, so sorted output is
  visibly non-monotonic (rows print as `2`, `3`, `1`). The number always
  means the Index line, never the row position.
- Ties keep Index order (stable sort), in both directions.
- **`date` key**: the first date token on the line; on an archived line,
  the first date token after the `x <completion-date>` prefix.
  *Caveat*: a line with no date token sorts into an **undated bucket
  that is always last**, so `--sort date -r` is not a byte-for-byte
  reversal of `--sort date`. Pre-append `todo.txt` files (and every
  hand-written line) frequently lack a date token.
- **`priority` key**: `(A)`..`(Z)` in order, unprioritised **last**. A
  missing priority is not "highest".
- Buckets (undated, unprioritised) stay last under `--reverse`: only the
  sortable block is reversed, so `--sort priority -r` still shows
  prioritised work first.
- `-r` without `--sort` is just reversed Index order - one rule, no
  special case. On a pre-append (reverse-chronological) file it is the
  cheapest way to read oldest-first.
- There is no `--sort hash`: an 8-hex token has no ordering meaning, and
  file order already provides a stable arbitrary order. There is no `-s`
  short flag for `--sort` (deferred, hash:50000d8e).

## todo.txt key value pairs

Here is a breakdown of the key-value pairs and metadata tags utilized by the local issue tracker's extended `todo.txt` format:

  * **`hash:<ID>`** (Custom Key-Value)
    The core linking mechanism of the tool. It maps a `todo.txt` index line directly to its sibling directory inside `.issues/<hash>/` (e.g., `hash:7a4f9b21`). `show` prints the ready-to-paste explicit form as a `Hash Token : hash:<hex>` line, so an identifier never has to be reassembled from the `hash:` token in the index line (and a digit-only hash is never mistaken for a line number). Storing the hash explicitly ensures that if you edit or update the issue title in the index file, the underlying description, comments, and attachments remain permanently and unambiguously attached.
  * **Priority `(A)` through `(Z)`** (Standard Prefix Notation)
    Placed at the very beginning of the index line to indicate urgency (e.g., `(A)` for critical issues, `(B)` for normal tasks). The CLI parses this for filtering (`list -p` / `--priority-filter`, a spec like `A-C`) and sorting (`list --sort priority`).
  * **Project Tags (`+<project>`)** (Standard `todo.txt` Metadata)
    Used to group issues under specific subsystems, modules, or features within your repository (e.g., `+backend`, `+auth`).
  * **Context Tags (`@<context>`)** (Standard `todo.txt` Metadata)
    Used to categorize issues by category, environment, or task type (e.g., `@bug`, `@enhancement`, `@cli`).

## How the hash is created

`add` and the close-time mint for hand-written lines share one function
(`generate_hash` in `todo.py`):

```text
hash = sha256_hex( title_utf8 + local_iso_timestamp )[:8]
```

  * `title` is the issue title as UTF-8. For close-time minting of a
    hand-written line it is the title parsed from that line: the
    `hash:` token onward is cut, leading priority and date tokens are
    dropped, and the remaining words are re-joined with single spaces
    (so runs of whitespace collapse before hashing).
  * `local_iso_timestamp` is `datetime.datetime.now().isoformat()` in
    local time (microseconds included when non-zero, e.g.
    `2026-11-07T13:49:02.123456`), taken at mint time and never stored.
  * The result is the first 8 characters of the lowercase hex SHA-256
    digest, so a hash is always 8 chars of `[0-9a-f]`.

Consequences:

  * The hash is not a function of the title alone: adding the same
    title twice yields two different hashes. It is also independent of
    the line number, so reordering `todo.txt` renames nothing.
  * An 8-char prefix is 32 bits of digest space, so collisions are
    possible in principle. Every minting path (`add`, `hash`, and the
    close-time mint) retries against the hashes already present in
    `todo.txt` and `done.txt`, and fails loudly after 10 tries, so a
    duplicate token can never enter the Index.
  * Hashes are not reproducible (local clock, microsecond resolution)
    and nothing re-derives them: the `hash:` token in the Index, or in
    `done.txt` after closing, is the only record.

## Minting hashes for hand-written lines

Because `todo.txt` is a plain text file, lines can be written by hand
without a `hash:` token. An **Unhashed Line** has no details directory
and no identifier: `show` / `comment` / `edit` refuse it, and `close`
mints a hash at close time so the archived line is addressable.

`todo.py hash` mints hashes for them on demand:

```text
todo.py hash                 # every Unhashed Line in todo.txt
todo.py hash 7               # one line, by line number
todo.py hash "some title"    # one line, by title substring
```

- The minted token is **appended at the end of the line**
  (`... some title hash:1a2b3c4d`), not inserted before the
  `+project` / `@context` tags. Appending keeps the derived title
  unchanged, so existing title-substring identifiers keep resolving.
- Already-hashed lines are never touched, so `hash` is idempotent. When
  there is nothing to mint it prints `nothing to mint` and does not
  write the file at all.
- Targeting an already-hashed line is an error (exit 1), as is an
  ambiguous title match among Unhashed Lines.
- Minted hashes are retried until unique across the hashes in
  `todo.txt` and `done.txt` (10 tries), then the command fails loudly.
  `add` and the close-time mint do the same.
- `todo.txt` only: `done.txt` has no backfill yet. No `.issues/<hash>/`
  directory is created - a repaired line stays title-only, and the
  directory appears on the first comment or `edit`.
- No `--dry-run`: `todo.txt` is versioned, so `git diff` is the
  preview, and the command prints one line per minted entry.

## Suppressing the editor launch

`edit` spawns `$EDITOR` / `$VISUAL` (or `vim`, `nano`, `vi`, `notepad`).
Batch and CI shells rarely want that, so a non-empty `TODO_NO_EDITOR`
suppresses the launch:

```text
TODO_NO_EDITOR=1 todo.py edit 3   # Error: editor launch disabled by $TODO_NO_EDITOR
```

- It suppresses **launching an editor**, nothing else: no process is
  started, and `edit` fails loudly instead (exit 1, no silent success).
- Any non-empty value suppresses; `0` and `false` do too (no value
  parsing). Unset or empty leaves the launch enabled.
- The check runs **before** any side effect: a refused `edit` creates no
  `.issues/<hash>/` directory and no bootstrap `issue.md`.
- Only `edit` reads it; no other command spawns an editor.

## File Layout

```text
/
+-- todo.txt                # Active issues index
+-- done.txt                # Archived/completed issues
+-- todo.py                 # Core CLI script
+-- test_todo.py            # Standard library test suite
+-- .issues/                # Created lazily, per issue with details
    +-- a1b2c3d4/           # Unique issue hash directory
        +-- issue.md        # Extended description
        +-- comments/       # 20261106_2130.md
        +-- attachments/    # Binary assets, logs, screenshots
