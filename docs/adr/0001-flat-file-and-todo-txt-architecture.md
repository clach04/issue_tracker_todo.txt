# Flat-File and Extended todo.txt Architecture

We are building a local issue tracker using a root `todo.txt` file for indexing and a sibling `.issues/<hash>/` directory structure for rich details, comments, and attachments.

## Decision

1. **Python Implementation**: Written in Python for broad portability and ease of maintenance without heavy binary compilation.
2. **Extended todo.txt Format**: Use standard single-line `todo.txt` convention extended with custom key-value pairs (e.g., `hash:ABC12345`) to preserve grep-friendliness and editor compatibility.
3. **Flat-File Details**: Avoid mail formats (`mbox`/`maildir`) in favor of direct markdown files for the issue body and ISO timestamp-named markdown files (`YYYYMMDD_HHMM.md`) for chronological comments.
