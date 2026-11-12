Test ideas for md2todo.py fence handling that were considered but not implemented (hash:4ae2da8b, hash:40f5fad4): (1) inline fence with a close marker run LONGER than the opener (e.g. "```x``````") - should the trailing run be treated as the close marker, or must the close run be exactly the same length as the open marker? GFM requires the closing fence to be at least as long as the opening fence; the current code accepts any 3+ run of the same char. Decide and document. (2) inline fence with a close run of the OTHER character (e.g. "```x~~~") - should the close run be the same char as the opener, or any fence char? Current code requires the same char (marker * 3). (3) inline fence with a close run of the same char but the open marker run is longer than the close run (e.g. "``````x```") - what does the close run need to be, exactly 4 backticks or any 3+? (4) inline fence with a close run of the same char but the open marker run is longer than the close run (e.g. "```x````") - what does the close run need to be, exactly 4 backticks or any 3+? Decide and document. (5) inline fence with the close run at line end but with trailing spaces after the close run (e.g. "```x```   ") - current code accepts trailing spaces (line.strip() and line.rstrip() both strip them). (6) a fence marker line with an info string that contains a fence marker run (e.g. "```python -c \"print(1)\"```") - the current code treats the line as an inline fence only if the line ends with a 3+ run of the same char as the opener. Test that the info string is not confused with the close marker. (7) a fence marker line with content between the open and close markers that contains a fence marker run (e.g. "```x```x```") - the current code treats the line as an inline fence (open+close on the same line); the content "x```x" is fence content. Test that the close marker is the LAST run, not the first. (8) nested fence: an inline fence inside an open fence (e.g. line 1 opens a fence, line 2 is an inline fence, line 3 closes the fence) - current code: the inline fence is fenced, and the fence state is not opened; the open fence stays open. Test that the fence state is not corrupted by the inline fence. All these are edge cases; the current behavior is correct for the common cases (test_inline_fence_is_self_contained, test_indented_bare_fence_marker_is_not_inline). Spawned from hash:4ae2da8b (commit 5c47461); related: hash:40f5fad4 (fail hard on unclosed fence).
Progress (2026-11-12): cheap cases (5), (6), (7), (8) done:
- (5) trailing spaces after the close run: test_inline_fence_trailing_spaces - OK
- (6) info string with fence run: test_inline_fence_info_string_with_fence_run - OK
- (7) close marker is the LAST run: test_inline_fence_close_run_is_last_run - OK
- (8) inline fence inside an open fence: test_inline_fence_inside_open_fence -
  found a REAL BUG: the fence-close check accepted a fence-marker line WITH
  content (e.g. '```x```') as a closer. GFM requires the closing fence to be
  bare (only whitespace after). Fixed in md2todo.py _fenced_flags and
  _unclosed_fence_line: only a bare marker line closes an open fence.
- (2) close run of the OTHER char: test_inline_fence_close_char_mismatch_opens_fence -
  the tilde close run does NOT close the backtick fence (GFM requires the
  same char), so the fence stays open to EOF and the import fails hard
  (hash:40f5fad4). The original expectation was wrong; the test now expects
  the failure.
Remaining (more effort): (1) close-run length vs opener length, (3) close-run
length with a longer opener, (4) close-run length variants. These need a
decision on the close-run length rule (GFM: "at least as long as the opening
fence") and a code change to _fenced_flags/_unclosed_fence_line.
131 tests OK (test_todo.py), 38 OK (test_webui.py); repro file unchanged
(90 issues).
