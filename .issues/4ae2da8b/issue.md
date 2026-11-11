md2todo.py fence detection treats a line with a fence marker at BOTH ends (e.g. line 125 of codgent_2e4c42b202c1471bae09511de7fd77a4ee138c9d_TODO.md: "    ```[tool] ask_user_question {...}]}]}```") as opening a fence that stays open until the next fence marker on its own line (line 659, the "Killed" log fence). The fence run 125-659 swallows 73 top-level "- [ ]" items; the intended fence at 659-662 is consumed as the wrong closer. Result: 18 items parsed instead of 136; dry-run shows "would import 10 issue(s): 9 open, 1 closed" instead of ~80. The user intends inline fences (Python-string-literal style, seen in the wild) to be self-contained: marker at start + close marker at end of the SAME line = fenced block, content = the rest of the line. Not standard GFM (GFM requires the closing fence alone on its line), but confirmed as the wanted behavior. Repro: python3 md2todo.py --dry-run codgent_2e4c42b202c1471bae09511de7fd77a4ee138c9d_TODO.md (file in repo root). Diagnostic note: hash:63f1914a; prior related: hash:6e6ac366 (closed not-a-bug).

Fence-balance sanity check (2026-11-11): the file has 13 fence markers
(lines 4, 9, 125, 659, 662, 774, 814, 840, 844, 900, 941, 946, 952).
Under GFM/old code, line 125 opens a fence and pairs with line 659,
which cascades the pairing: 125->659, 662->774, 814->840, 844->900,
941->946, 952 unclosed (odd). That is the "unbalanced ```" symptom
under the old code. Under the new inline-fence rule, line 125 is
self-contained, so the remaining 12 markers pair up cleanly: 4->9,
659->662, 774->814, 840->844, 900->941, 946->952. 6 pairs + 1 inline =
13 markers = balanced. The fence-balance finding is the same root cause
as the inline-fence bug; the inline fence misclassified as an opener
made the fence pairing cascade and left 952 dangling.

Fixed 2026-11-11 (hash:4ae2da8b): inline fences are self-contained in
md2todo.py._fenced_flags. A fence marker at line start + close marker at
the end of the SAME line = fenced block, no fence state opened. Detection
uses line.strip() (not rstrip()): the close marker must be the last
non-space run AND the line must have content beyond the bare marker, so
an indented bare fence marker alone on its line still opens a fence.
First attempt compared line.rstrip() (kept indentation) and misclassified
every indented '```' as inline; caught by the second regression test.

Repro numbers after fix: 90 issues (74 open, 16 closed), 154 items parsed
(was 18), 90 roots (was 18). The 73 top-level "- [ ]" + 19 "- [x]" column-0
lines are all parsed; the 2 fenced Convention lines (5-6) are excluded.
Fence runs now: 4-9, 125-125 (inline), 659-662, 774-814, 840-844, 900-941,
946-952. The 'Killed' log fence (659-662) is fenced again.
Tests: 2 new regression tests in test_todo.py (test_inline_fence_is_
self_contained, test_indented_bare_fence_marker_is_not_inline); 123 tests
OK (test_todo.py), 38 OK (test_webui.py).