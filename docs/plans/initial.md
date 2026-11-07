# Local Issue Tracker CLI Specification

This document outlines the command-line interface (CLI) specification for the Python-based local repository issue and bug tracking system. The tool provides robust management over a human-readable, grep-friendly `todo.txt` index while maintaining rich markdown descriptions, timestamped comments, and attachments in sibling `.issues/<hash>/` directories.

---

## Architecture & File Layout

* **`todo.txt`**: Root-level index of active issues (one line per issue).
* **`done.txt`**: Root-level archive of completed issues (migrated automatically upon closure).
* **`.issues/<hash>/`**: Directory for each issue, containing:
* `issue.md`: The primary issue body/description.
* `comments/`: Directory storing chronological comment files named with ISO timestamps (e.g., `20261106_2130.md`).
* `attachments/`: Folder for associated files, screenshots, or logs.



---

## Core Command Reference

### 1. `add` — Create a New Issue

Initializes a new issue record, generates a unique short hash, adds an entry to `todo.txt`, and creates the corresponding `.issues/<hash>/` directory structure with an initial `issue.md`.

* **Syntax**: `todo add "<title>" [-d "<description>"] [-p <priority>]`
* **Arguments**:
* `<title>`: The short summary/title of the issue (required).


* **Options**:
* `-d`, `--description`: Optional extended description body written directly to `.issues/<hash>/issue.md`. If omitted, a blank template or title-only file is created.
* `-p`, `--priority`: Optional priority letter (e.g., `A`, `B`, `C`) conforming to standard `todo.txt` conventions.


* **Behavior**:
1. Computes a unique short hash (e.g., 8-character `sha256` prefix).
2. Appends a new line to `todo.txt` containing the creation date, priority (if given), title, and custom key-value metadata (e.g., `hash:ABC12345`).
3. Creates `.issues/<hash>/` with an `issue.md`, `comments/`, and `attachments/`.



---

### 2. `list` / `ls` — Query Active Issues

Lists open issues currently tracked in `todo.txt` with optional filtering and sorting.

* **Syntax**: `todo list [--status <open|closed>] [--priority <p>] [--sort <field>]`
* **Options**:
* `--status`: Filter by `open` (reads `todo.txt`, default) or `closed` (reads `done.txt`).
* `-p`, `--priority`: Filter by priority tier.
* `--sort`: Sort output by date, priority, or hash.


* **Behavior**: Parses `todo.txt` (or `done.txt`), parses key-value pairs, and displays a clean, formatted table or list in the terminal.

---

### 3. `show` — Inspect Issue Details

Displays the full issue summary, metadata, current description from `issue.md`, and all chronological comments.

* **Syntax**: `todo show <hash-prefix>`
* **Arguments**:
* `<hash-prefix>`: Full or unambiguous partial hash of the issue.


* **Behavior**:
1. Locates the issue directory matching the hash prefix inside `.issues/`.
2. Renders the issue title, status, metadata tags, contents of `issue.md`, and lists any files in `comments/` and `attachments/` in chronological order.



---

### 4. `comment` — Add a Timestamped Comment

Appends a new comment to an issue.

* **Syntax**: `todo comment <hash-prefix> "<comment-text>"`
* **Arguments**:
* `<hash-prefix>`: Target issue hash.
* `<comment-text>`: The markdown-formatted text of the comment.


* **Behavior**:
1. Generates an ISO timestamp filename using format `YYYYMMDD_HHMM.md` (e.g., `20261106_2130.md`).
2. Writes the comment text into `.issues/<hash>/comments/20261106_2130.md`.



---

### 5. `close` — Complete and Archive an Issue

Marks an issue as completed, moving its index line from `todo.txt` to `done.txt`.

* **Syntax**: `todo close <hash-prefix>`
* **Arguments**:
* `<hash-prefix>`: Target issue hash.


* **Behavior**:
1. Locates the issue line in `todo.txt`.
2. Prepends completion status (`x YYYY-MM-DD`) according to the `todo.txt` specification.
3. Moves the line from `todo.txt` to the bottom of `done.txt`.
4. Keeps the detailed `.issues/<hash>/` folder intact for permanent historical reference.



---

### 6. `edit` — Direct File Editing Helper

Convenience command to open an issue's description file in your default system editor (`$EDITOR`).

* **Syntax**: `todo edit <hash-prefix>`
* **Arguments**:
* `<hash-prefix>`: Target issue hash.


* **Behavior**: Opens `.issues/<hash>/issue.md` using `os.execvp` with `$EDITOR` (falling back to `nano` or `vi`).

---

## Extended `todo.txt` Format Specification

Each entry in `todo.txt` follows a strict single-line format augmented with custom key-value pairs:

```text
[priority] [creation-date] [Title text...] hash:<ID> project:@<proj> context:+<ctx>

```

* **Example Active Item**:
```text
(A) 2026-11-06 Fix login redirection bug hash:7a4f9b21 +auth @backend

```


* **Example Closed Item (in `done.txt`)**:
```text
x 2026-11-06 2026-11-05 Fix login redirection bug hash:7a4f9b21 +auth @backend

```
