# Local Issue Tracker

A lightweight, local-first issue and bug tracking system for repositories using extended todo.txt syntax and flat files.

## Language

**Issue**:
A distinct unit of work, bug report, or task tracked within the local repository.
_Avoid_: Ticket, item, bug

**Index**:
The root `todo.txt` file tracking all open tasks and their core properties in a single line per issue.
_Avoid_: Database, manifest, registry

**Details Directory**:
The sibling `.issues/<hash>/` directory storing the primary markdown body, timestamped comments, and attachments.
_Avoid_: Payload folder, blob store

**Identifier**:
A single token given to an issue command that resolves to exactly one Issue. May be an Index line number, a hash prefix, a title fragment, or an Explicit Hash Form.
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
