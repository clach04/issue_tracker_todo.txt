# ADR-0007: Web UI server backend is anywsgi-first with stdlib fallback

Web UI for the tracker (hash:51e9e387) needs a WSGI server. The user's
reference snippet uses anywsgi (https://github.com/clach04/anywsgi-py) with a
wsgiref fallback. The project is stdlib-only.

## Decision

`todo_webui.py` tries `anywsgi` first and falls back to
`wsgiref.simple_server` when anywsgi is unavailable. The WSGI application
function is written backend-agnostic so it works under either.

## Consequences

- anywsgi is NOT installed in this environment and must not be fetched
  (user instruction). All testing exercises the fallback path; the
  anywsgi path is verified by the user wherever anywsgi is installed.
- The wsgiref fallback is development-grade (single-threaded); it is the
  default path here, which is acceptable for a local-first read-only
  tool bound to 127.0.0.1.
- No new dependencies enter the tree; anywsgi remains an optional
  upgrade, mirroring the project's stdlib-only rule.

## Considered Options

- Pure stdlib wsgiref only: simplest, but the user explicitly wants the
  anywsgi-first snippet style.
- anywsgi as a hard dependency: rejected; would break the stdlib-only
  rule and require installing anywsgi here.
