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
