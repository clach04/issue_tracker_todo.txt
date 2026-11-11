# Web UI copy-to-clipboard for todo.txt rows and show view

Status: done 2026-11-10 - copy buttons shipped on / (hash rows incl.
done.txt) and /show metadata block; hover-reveal, execCommand fallback,
prompt last resort; mobile deferred to hash:0649b64e.

Source: hash:70be6f02 (from hash:0a7d7e68 discussion). Client-side
clipboard copy, consistent with the ADR-0008/0009/0010 pattern.

## Decisions

- Copied text: `hash:<hex>` token only (e.g. `hash:abc12345`) - user
  adds the command themselves.
- Visibility: hover-reveal on desktop (CSS `:hover`); mobile explicitly
  skipped (TODO filed, see below).
- Mechanism: `navigator.clipboard.writeText` first; fallback to hidden
  textarea + `document.execCommand('copy')` (plain http:// LAN origins
  are not a secure context, so the async Clipboard API is unavailable);
  last resort `window.prompt` showing the text for manual copy.
- No-JS fallback: no button (server markup unchanged).
- Button: small `copy` link after each row on the / list page; on the
  /show page next to the Hash Token in the metadata block.
- Feedback: button text changes to `copied` for ~1s after success.

## TODO items

- [x] Add TODO item for mobile support (hover-reveal does not work on
      touch devices) - filed as hash:0649b64e.
- [x] `webui.js`: add copy buttons (list rows + show page), clipboard
      chain with fallbacks, feedback text (webui.js 5.9KB).
- [x] `todo_webui.py`: add copy button markup (span.todotxt rows + done.txt
      rows + show page metadata block), CSS for hover-reveal.
- [x] Tests: buttons present on / and /show; no-JS fallback unchanged;
      copied text is the hash: token (verified via the button's data
      attribute).
