# `todo.py comment` stdin support (dash marker)

Status: done 2026-11-09 - shipped in one session: dash marker, binary
read/write, conflict/empty/TTY errors, 6 new tests (103 total), README
section, CONTEXT.md Dash Marker term. Deferred: hash:4e270ef0,
hash:fef2d86f, hash:cbe3727f.

Grilled 2026-11-09 from hash:2d004b8f. All decisions below are settled;
spawned issues: hash:4e270ef0 (editor comment add/edit, deferred),
hash:fef2d86f (`add -d` stdin, deferred), hash:cbe3727f (text-mode stdin
follow-up, deferred).

Let `todo.py comment` accept a comment body from Standard Input, so
`cat notes.md | todo.py comment hash:2d004b8f` and
`curl URL | todo.py comment hash:2d004b8f` work.

## Design

### Trigger

- The `text` positional argument stays **required**. A new value `-`
  (the **Dash Marker**) means "read the comment body from Standard
  Input".
- `todo.py comment <id> -` reads stdin. `todo.py comment <id>` with no
  text arg still fails as today (argparse arity).
- `todo.py comment <id> "text"` unchanged: text argument used verbatim.
- Literal `-` as a comment body is an accepted limitation: there is no
  escape mechanism. Document it.

### Conflicts

- Text arg + piped stdin is a **loud error** (exit 1, no comment file
  created). Detect via `sys.stdin.isatty()` (False when piped, even
  from a file redirect). This blocks the curl-URL use case but keeps
  ambiguity zero.

### Reading and writing

- Read `sys.stdin.buffer` (bytes), write in binary mode. Byte fidelity,
  no text-mode translation, no encoding validation.
- Empty stdin (0 bytes) is a **loud error** (exit 1, no comment file
  created).
- Write the bytes as-is: no header block, no newline normalization.
- Filename and location unchanged: `.issues/<hash>/comments/<UTC
  timestamp>.md` via the existing `cmd_comment` path. `show` prints it
  as-is.

### Scope

- `comment` only. No other command accepts stdin (deferred: hash:fef2d86f
  for `add -d`, hash:4e270ef0 for editor-driven comment creation/edit).
- No editor involvement: TODO_NO_EDITOR is irrelevant here.

## Implementation

1. `cmd_comment` in `todo.py`: if `args.text == "-"`, read stdin
   (bytes, error on conflict/empty), write binary. Else existing path.
2. `parser_comment` help text updated to mention the dash marker.
3. README.md: document the dash marker under a new short section
   (near "Suppressing the editor launch"), including the literal `-`
   limitation and the conflict error.
4. CONTEXT.md: add "Dash Marker" term (vocabulary only).
5. test_todo.py: stdin-piped comment, text-arg comment, conflict error,
   empty-stdin error, literal handling of `-` as documented limitation.

## Done when

- All five implementation items shipped.
- hash:2d004b8f closed with the plan hash in the closing line.
- Spawned issues remain open (deferred, explicitly named here).
