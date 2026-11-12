Test ideas for md2todo.py fence handling that were considered but not implemented (hash:4ae2da8b, hash:40f5fad4): (1) inline fence with a close marker run LONGER than the opener (e.g. "```x``````") - should the trailing run be treated as the close marker, or must the close run be exactly the same length as the open marker? GFM requires the closing fence to be at least as long as the opening fence; the current code accepts any 3+ run of the same char. Decide and document. (2) inline fence with a close run of the OTHER character (e.g. "```x~~~") - should the close run be the same char as the opener, or any fence char? Current code requires the same char (marker * 3). (3) inline fence with a close run of the same char but the open marker run is longer than the close run (e.g. "``````x```") - what does the close run need to be, exactly 4 backticks or any 3+? (4) inline fence with a close run of the same char but the open marker run is longer than the close run (e.g. "```x````") - what does the close run need to be, exactly 4 backticks or any 3+? Decide and document. (5) inline fence with the close run at line end but with trailing spaces after the close run (e.g. "```x```   ") - current code accepts trailing spaces (line.strip() and line.rstrip() both strip them). (6) a fence marker line with an info string that contains a fence marker run (e.g. "```python -c \"print(1)\"```") - test that the info string is not confused with the close marker. (7) a fence marker line with content between the open and close markers that contains a fence marker run (e.g. "```x```x```") - the content "x```x" is fence content; test that the close marker is the LAST run, not the first. (8) nested fence: an inline fence inside an open fence (line 1 opens a fence, line 2 is an inline fence, line 3 closes the fence) - test that the fence state is not corrupted by the inline fence. All these are edge cases; the current behavior is correct for the common cases (test_inline_fence_is_self_contained, test_indented_bare_fence_marker_is_not_inline). Spawned from hash:4ae2da8b (commit 5c47461); related: hash:40f5fad4 (fail hard on unclosed fence).

Progress (2026-11-12): cheap cases (5), (6), (7), (8) done.

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

Remaining (more effort): cases (1), (3), (4) close-run length rule.

131 tests OK (test_todo.py), 38 OK (test_webui.py); repro file unchanged
(90 issues).

Recommendations (Codgent z-ai/glm-5.3-flash thinking: high, 2026-11-12):

- (1) close-run length vs opener length: adopt GFM's "at least as long as
  the opening fence" rule. The close run must be the same char as the
  opener and >= the opener's length. This means "```x``````" is inline
  (close run 6 >= opener 3), but "``````x```" is NOT inline (close run 3 <
  opener 6) - it opens a fence with a 6-backtick marker. The current code
  accepts any 3+ run of the same char as the close run, which is looser
  than GFM. Recommend: match GFM (close run >= opener run length).
- (3) close-run length with a longer opener: same rule as (1) - close run
  must be >= the opener's length. "``````x```" is not inline; the close
  run of 3 is shorter than the opener of 6.
- (4) close-run length variants: same rule as (1) - "```x````" is inline
  (close run 4 >= opener 3). "```x```" is inline (close run 3 == opener 3).
- Effort estimate: 1-2 hours including the decision write-up. The change
  is localized to _fenced_flags and _unclosed_fence_line (compare the
  close-run length against the opener's length, not just >= 3).
- Recommendation: defer cases (1), (3), (4) unless a real-world file hits
  them. The current behavior is deterministic and documented; the GFM
  rule is a nice-to-have for exotic edge cases. Revisit if a real file
  shows up with a long opener run.
