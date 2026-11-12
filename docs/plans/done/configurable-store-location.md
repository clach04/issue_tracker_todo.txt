# Configurable Store Location (--dir / --file, env vars)

Status: done 2026-11-11 - implemented --dir/--file + env vars across todo.py, webui, md2todo; ADR-0017; README section.

Implements ADR-0017 and issue hash:9efddab9. The store is a bundle
(`todo.txt` + `done.txt` + `.issues/`) relocated as a unit.

## Decisions (settled in grill session 2026-11-08)

- `--dir` (env `TODO_TRACKER_DIR`) relocates the bundle dir; file
  names fixed. Relative resolves against cwd; absolute allowed.
- `--file` (env `TODO_FILE`) points at the todo index by name or full
  path. Full path implies its parent dir for the whole bundle
  (done.txt and .issues/ move there). Bare name only changes the name.
- `--file` (full path) wins over `--dir`; `--dir` still applies when
  `--file` is a bare name.
- Precedence: CLI flags > env vars > defaults.
- One shared helper in `todo.py` (e.g. `todo.apply_store(dir, file)`)
  resolves precedence and mutates module constants; `todo.py` reads
  env vars at import time into defaults. webui and md2todo call the
  same helper after their own parse_args.
- webui and md2todo get the same `--dir`/`--file` flags; md2todo's
  positional `file` is renamed to `input` (breaking change).
- Missing store dir auto-created (`mkdir -p`).
- Messages use the configured file name dynamically (no hardcoded
  `todo.txt` in messages).

## TODO

- [x] todo.py: add module-level `apply_store(dir=None, file=None)`
      helper; resolve precedence, normalize paths, mutate
      TODO_FILE/DONE_FILE/ISSUES_DIR constants. Called from main()
      after parse_args.
- [x] todo.py: add `--dir` and `--file` to the shared `common` argparse
      parent (or a separate shared parser) so every subcommand gets them.
- [x] todo.py: replace hardcoded `todo.txt`/`done.txt` strings in
      error/output messages with the constants.
- [x] todo_webui.py: add `--dir`/`--file` flags (flag+env override
      convention, like LISTEN_ADDRESS); call `todo.apply_store` after
      parse_args; verify cwd-relative paths (os.getcwd() usage) follow
      the resolved constants.
- [x] md2todo.py: rename positional `file` to `input`; add
      `--dir`/`--file`; call `todo.apply_store`.
- [x] Tests: precedence (flag > env > default), --file full-path
      derivation of done.txt/.issues, --dir + bare --file combo,
      auto-create of missing dirs, dynamic message names.
- [x] README.md: document the new options, env vars, and the bundle
      model; note md2todo positional rename as breaking.
- [x] Close issue hash:9efddab9 when done.
