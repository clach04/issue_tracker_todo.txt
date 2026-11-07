# Local Issue Tracker (`todo.py`)

A lightweight, local-first issue and bug tracking system for repositories that combines the simplicity of `todo.txt` with rich flat-file descriptions, timestamped comments, and attachments.

Designed for developers who want a fast, grep-friendly, dependency-free tracker living directly inside their git repository.

---

## Features

  - **Standard Library Only**: Written in pure Python, compatible with both **Python 2 (2.7+)** and **Python 3**. No external dependencies required!
  - **`todo.txt` Compatible Index**: Open tasks live in a human-readable `todo.txt` file at your repo root, extended with clean custom metadata (`hash:ABC12345`).
  - **Automatic Archiving**: Closed issues migrate automatically from `todo.txt` to `done.txt`, keeping your active view clean and lightweight.
  - **Rich Flat-File Details**: Every issue gets its own sibling `.issues/<hash>/` directory containing:
    - `issue.md`: The primary issue body/description.
    - `comments/`: Chronological comment markdown files named with ISO timestamps (`YYYYMMDD_HHMM.md`).
    - `attachments/`: A dedicated folder for screenshots, logs, or associated files.

---

## todo.txt key balue pairs

Here is a breakdown of the key-value pairs and metadata tags utilized by the local issue tracker's extended `todo.txt` format:

  * **`hash:<ID>`** (Custom Key-Value)
    The core linking mechanism of the tool. It maps a `todo.txt` index line directly to its sibling directory inside `.issues/<hash>/` (e.g., `hash:7a4f9b21`). Storing the hash explicitly ensures that if you edit or update the issue title in the index file, the underlying description, comments, and attachments remain permanently and unambiguously attached.
  * **Priority `(A)` through `(Z)**` (Standard Prefix Notation)
    Placed at the very beginning of the index line to indicate urgency (e.g., `(A)` for critical issues, `(B)` for normal tasks). The CLI parses this for filtering and sorting via `-p` / `--priority`.
  * **Project Tags (`+<project>`)** (Standard `todo.txt` Metadata)
    Used to group issues under specific subsystems, modules, or features within your repository (e.g., `+backend`, `+auth`).
  * **Context Tags (`@<context>`)** (Standard `todo.txt` Metadata)
    Used to categorize issues by category, environment, or task type (e.g., `@bug`, `@enhancement`, `@cli`).

## File Layout

```text
/
+-- todo.txt                # Active issues index
+-- done.txt                # Archived/completed issues
+-- todo.py                 # Core CLI script
+-- test_todo.py            # Standard library test suite
+-- .issues/
    +-- a1b2c3d4/           # Unique issue hash directory
        +-- issue.md        # Extended description
        +-- comments/       # 20261106_2130.md
        +-- attachments/    # Binary assets, logs, screenshots
