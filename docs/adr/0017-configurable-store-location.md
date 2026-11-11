# Configurable Store Location: env vars + --dir/--file

Issue hash:9efddab9 asks for options to specify the todo.txt file name
and/or directory. Today `todo.py` hardcodes `TODO_FILE = 'todo.txt'`,
`DONE_FILE = 'done.txt'`, `ISSUES_DIR = '.issues'`; the web UI and
`md2todo.py` import `todo` and use the same constants. The decisions
below were settled in a grill session (2026-11-08).

## Decision

**The store is a bundle: `todo.txt` + `done.txt` + `.issues/` all live
in one directory.** The bundle is relocated as a unit; a store never
splits across directories.

**Two knobs:**

- `--dir` (env `TODO_TRACKER_DIR`): relocate the bundle directory.
  File names stay fixed. Relative values resolve against cwd; absolute
  paths are allowed (a store may live outside any repo, e.g. `~/notes`).
- `--file` (env `TODO_FILE`): point at a specific todo index file by
  name or full path. A full path implies its own parent directory for
  the whole bundle: `--file /home/me/notes/issues.txt` puts
  `done.txt` at `/home/me/notes/done.txt` and `.issues/` at
  `/home/me/notes/.issues/`. A bare file name only changes the name
  inside the resolved directory.

**`--file` wins over `--dir`** when both are given and `--file` is a
full path. `--dir` is still meaningful when `--file` is a bare name
(`--file issues.txt --dir notes`).

**Precedence order: CLI flags override env vars, which override the
defaults (`todo.txt` / `done.txt` / `.issues` in cwd).**

**All three tools share one code path:** `todo.py` reads the env vars
once at import time into module constants, and exposes a small
resolve/apply helper (e.g. `todo.apply_store(dir=None, file=None)`)
that implements precedence and mutates the constants. `todo.py` calls
it after `parse_args`; `todo_webui.py` and `md2todo.py` call the same
helper after their own `parse_args`. Webui and md2todo also get the
same `--dir`/`--file` flags (webui already follows the flag+env
override convention via `--listen-address`/`LISTEN_ADDRESS`).

**Consequence for md2todo.py:** its positional argument is renamed
from `file` to `input` (breaking change to its CLI) so `--file` is
unambiguous there.

**Missing directories are auto-created (`mkdir -p`).** A non-existent
store dir is a valid empty tracker, matching the existing
`ensure_environment()` behavior. A typo path is silently created - a
real but accepted trade-off.

**Error and output messages use the configured file name dynamically**
(`'line {} out of range in {}'` interpolates the constant), so they
stay truthful when the store is renamed. No hardcoded `todo.txt`
strings in messages.

## Alternatives rejected

- **Repo-root only** (reject absolute paths): keeps the store inside
  the repo, but blocks legitimate use of a store outside any repo.
- **`--todo-file`/`--todo-dir`**: more explicit, but longer; the
  `--file` env var name is `TODO_FILE` exactly as the user chose.
- **`TODO_TRACKER_FILE` env var**: safer against collisions with other
  tools' `TODO_FILE` conventions, but the user explicitly picked
  `TODO_FILE` for parity with the `--file` flag.
- **Per-tool precedence logic**: duplicated the rules in three places;
  rejected in favor of one shared helper in `todo.py`.
