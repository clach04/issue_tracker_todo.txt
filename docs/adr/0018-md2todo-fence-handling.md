# md2todo Fence Handling: Inline Fences Self-Contained, Bare-Marker Close

Imported GFM task lists contain fenced code blocks; a misdetected fence
swallows every checkbox item after it, silently losing issues (hash:6e6ac366
repro file: 13 markers, 82 items swallowed). Three decisions:

**Inline fences are self-contained (not GFM).** A fence-marker line with
content at line start AND a close run of the same char at line end (e.g.
` ```[tool] call {...}]}]}` ``) closes on the SAME line; no fence state
opens. Standard GFM requires the closing fence alone on its line, so the
GFM reading would leave the fence open and swallow the rest of the file.
The inline form is seen in the wild (the repro file had one) and matches
the user's intent; the deviation is deliberate.

**A bare marker line closes an open fence; a marker line with content does
not.** GFM: the closing fence must be alone on its line (only spaces
after it). The first implementation accepted any fence-marker line as a
closer, so ` ```x``` ` inside an open fence closed it - the content
belongs to the fence. The close run may be longer than the opener
(GFM: at least as long).

**An unclosed fence fails the import loudly** (line number of the opener
in the error). An unclosed fence has no valid interpretation; the old
behavior silently swallowed everything after it to EOF. The fix is to
close the fence in the source file, not to make the importer tolerant.

## Considered Options

- **Strict GFM inline fences** (inline fence stays open, swallows the
  file): rejected; the user's real files use the inline form and the
  user confirmed the inline reading is intended.
- **Warn-only on unclosed fence**: rejected; the failure mode is silent
  data loss, and a warning is easy to miss in a long import.
- **Close-run length must match the opener exactly**: rejected as
  unobservable in practice; GFM requires "at least as long", so the
  code accepts any run of the same char of length >= 3.

## Consequences

- Inline fences cannot span lines; a fence whose open marker has content
  at line start and close run at line end is a single line by definition.
- The close-run check is `line.strip() == marker * 3+` for openers: a
  bare marker line closes; a marker line with content does not.
- The close-run length rule (GFM: at least as long as the opener) is
  accepted but not length-verified; remaining edge cases are deferred
  (hash:bcdb0f31).

References: hash:4ae2da8b (inline fence fix, commit 5c47461), hash:40f5fad4
(fail hard on unclosed fence), hash:bcdb0f31 (deferred fence edge cases),
hash:6e6ac366 (the original bug report and its repro file).
