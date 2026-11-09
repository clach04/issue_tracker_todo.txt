# Local Issue Tracker

A lightweight, local-first issue and bug tracking system for repositories using extended todo.txt syntax and flat files.

## Language

**Issue**:
A distinct unit of work, bug report, or task tracked within the local repository.
_Avoid_: Ticket, item, bug

**Index**:
The root `todo.txt` file tracking all open tasks and their core properties in a single line per issue. By design small: a token too large to be an Index line number is not an Index.
_Avoid_: Database, manifest, registry

**Details Directory**:
The sibling `.issues/<hash>/` directory storing the primary markdown body, timestamped comments, and attachments.
_Avoid_: Payload folder, blob store

**Identifier**:
A single token given to an issue command that resolves to exactly one Issue. May be an in-range Index line number, a hash prefix, a title fragment, or an Explicit Hash Form.
_Avoid_: ID, key, reference

**Explicit Hash Form**:
An identifier written as `hash:<hex>` that names an Issue by its hash directly. Unambiguous by construction.
_Avoid_: Full hash ID

**Active List**:
The set of open Issues, indexed in the root `todo.txt`. Closed Issues leave the Active List and become the Archive.
_Avoid_: Open queue, backlog

**Archive**:
The set of closed Issues, appended to `done.txt`. Identifiers resolve against the Active List only; the Archive is reachable via hash.
_Avoid_: History, graveyard

**Unhashed Line**:
An Index line written by hand with no Explicit Hash. Outside the tracker's schema: it has no Details Directory and no Identifier, so it can only be Minted (at close, or by `hash`) or left alone.
_Avoid_: Raw line, bare entry, hashless todo

**Mint**:
To bestow an Identifier on an Unhashed Line. Happens at close time or on demand for the whole Index.
_Avoid_: Backfill, assign, generate hash

**Import**:
Converting a GFM task-list markdown file into Issues (the one-shot job of `md2todo.py`). Not a tracker operation: nothing in `todo.py` imports.
_Avoid_: Sync, migrate, convert

**Checklist Item**:
A GFM task-list line (`- [ ]` / `- [x]`) in an imported file. Becomes an Issue at top level; nested ones become part of the parent's issue.md.
_Avoid_: Task, sub-task, checkbox

**GFM Task List**:
The GitHub-Flavored Markdown checklist syntax: a list marker with a `[ ]`/`[x]` checkbox, nestable by indentation. Source format for Import.
_Avoid_: Todo list, markdown checklist

**Editor Launch Suppressed**:
The state in which `edit` starts no editor process, because the environment variable `TODO_NO_EDITOR` is non-empty. Editing an Issue is not disabled: `issue.md` stays writable by any other means. The command itself fails loudly (exit 1) before any Details Directory side effect.
_Avoid_: Disabled editing, read-only issue, no-op edit, silent skip

**Dash Marker**:
The text argument `-` on `comment`: the comment body is read from Standard Input instead of the command line. A literal `-` body is not expressible; the conflict case (text arg plus piped input) is a loud error.
_Avoid_: Stdin flag, pipe mode, dash option
