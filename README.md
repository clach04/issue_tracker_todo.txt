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

## todo.txt key value pairs

Here is a breakdown of the key-value pairs and metadata tags utilized by the local issue tracker's extended `todo.txt` format:

  * **`hash:<ID>`** (Custom Key-Value)
    The core linking mechanism of the tool. It maps a `todo.txt` index line directly to its sibling directory inside `.issues/<hash>/` (e.g., `hash:7a4f9b21`). Storing the hash explicitly ensures that if you edit or update the issue title in the index file, the underlying description, comments, and attachments remain permanently and unambiguously attached.
  * **Priority `(A)` through `(Z)`** (Standard Prefix Notation)
    Placed at the very beginning of the index line to indicate urgency (e.g., `(A)` for critical issues, `(B)` for normal tasks). The CLI parses this for filtering and sorting via `-p` / `--priority`.
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
