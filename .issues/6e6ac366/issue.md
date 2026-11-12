# TODO.md conversion bug (2026-11-08)

(A) 2026-11-08 TODO.md conversion bug. see https://github.com/clach04/codgent/commit/b9dc1a0910b7cfa9421cf969e116bce4765012a3 where TODO.md had to be restored, many non-child issues ended up in a issues.md `grep '^\- \[ \] ' TODO.md  | wc -l` yields 64 rows but import yields `would import 80 issue(s): 65 open, 15 closed; 56 issue.md file(s)`  !! it reads in `open, not started` as a todo item, even though its in a backtick block! :-( @bug hash:6e6ac366

Closed 2026-11-11: not-a-bug. The parser is behaving correctly; the report's arithmetic is wrong:
- 64 `grep '^\- \[ \]'` rows = 63 open items (line 3 is inside the fence) + 17 top-level `- [x]` items the grep excluded = 80 issues
- 65 open = 63 + 2 `- [x]` items with unchecked descendants
- 15 closed = the other 15 `- [x]` items
- 56 issue.md = 80 - 24 bare checkbox lines with no content
Nothing is missing or lost. The fence content is excluded from items but copied verbatim into the first issue's issue.md as "preceding content" (verified: line 10's issue.md retains the fence markers; the fenced lines are not in todo.txt/done.txt).
Diagnostic note: hash:63f1914a.
