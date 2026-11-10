# Web UI for todo.txt + `.issues` (read-only v1)

Status: done

Source: hash:51e9e387 ("a web UI for reading (and writting/editing) todo.txt
and .issue resources would be REALLY helpful. v1 to implement 'show' by
clicking on todo.txt entries would be a good starting point"). Decisions
settled in a grill session 2026-11-08 (grill-ask); backend choice recorded in
docs/adr/0007-webui-anywsgi-first-with-stdlib-fallback.md.

## Scope

**Read-only v1.** No write operations (comment/close/edit) in v1; they are
the v2 work. No priority filters, no `--sort`, no done.txt listing view.

## Decisions

- **Entry point**: separate `todo_webui.py` importing `todo.py` as a module
  (same shape as md2todo.py). `todo.py` CLI untouched.
- **Backend**: anywsgi-first with stdlib `wsgiref` fallback (ADR-0007).
  anywsgi is NOT installed here; testing exercises the fallback path only.
- **Python 2.7 + Python 3** compatible, like todo.py.
- **Bind**: `127.0.0.1:8000` default; env `LISTEN_ADDRESS` / `LISTEN_PORT`
  override; `--listen-address` / `--port` flags override env. Never
  defaults to 0.0.0.0.
- **Serves the current working directory's** repo (todo.txt, done.txt,
  .issues/), exactly like todo.py.
- **Markdown**: escaped `<pre>` plain text. Deferred markdown rendering
  filed as a tracker issue (see TODO items below).

## Routes

- `/` - list open issues from `todo.txt`. Each line with a `hash:` token
  links to `/show/<hash>`. Unhashed lines render as plain text, no link.
- `/show/<hash>` - show page. Resolves via `todo.py`'s
  `resolve_identifier` (prefix allowed; ambiguous/unresolved -> 404 page).
  If that proves problematic in testing, switch to strict full-hash logic.
  Renders description + comments + attachments + a `closed` badge when the
  line lives in `done.txt` (closed issues reachable by hash, per
  `cmd_show`'s fallback).
- `/show?line=<n>` - line-number show, resolves against `todo.txt` only
  (open issues). Closed issues are reachable via hash, not line.
- `/show/<hash>/attachments/<name>` - serves attachment bytes as
  `application/octet-stream`; path strictly contained inside
  `.issues/<hash>/attachments/` (no traversal).

## Rendering

- Minimal inline CSS (one small `<style>` block; monospace, simple table).
- All markdown content rendered as HTML-escaped `<pre>`; no markdown lib.
  TODO: deferred markdown rendering - filed as tracker issue.

## Testing

- Direct WSGI application calls with a fake `environ` (no sockets,
  py2+py3 deterministic), plus one smoke test of the wsgiref fallback
  handler.

## TODO items

- [x] Implement `todo_webui.py` (routes, resolution reuse, rendering).
- [x] Test suite: direct WSGI calls + wsgiref fallback smoke.
- [x] Deferred markdown rendering (tracker issue, not this plan).
