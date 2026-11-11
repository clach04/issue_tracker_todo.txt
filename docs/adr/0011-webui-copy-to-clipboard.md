# ADR 0011: Web UI copy-to-clipboard for todo.txt rows and show view

Status: accepted

Context: hash:70be6f02. Users want to copy a hash: token from the web UI
to paste into shell commands (e.g. `todo.py show hash:abc12345`). The
web UI is read-only, client-side enhancement (ADR-0008/0009/0010).

Decision: copy button per row on the / list page and next to the Hash
Token on the /show page. The copied text is the `hash:<hex>` token only
(user adds the command). The button label is the copy icon U+29C9
(&#x29C9;). Visibility: always visible by default (`.copy-btn` display
inline, including no-JS users); inside table rows on the / list page it
is hover-reveal (`tr .copy-btn { display: none }`). Clipboard chain:
`navigator.clipboard` first, then a hidden textarea +
`document.execCommand('copy')` (plain http:// LAN origins are not a
secure context, so the async Clipboard API is unavailable), then
`window.prompt` as last resort. Feedback: button text changes to a
check/cross mark for ~1s. Mobile/touch devices are explicitly skipped
(hover-reveal does not work on touch); a separate TODO item tracks them.

Alternatives:
- Copy the full `todo.py show hash:...` command: more convenient, but
  the user may want a different command or just the token.
- Always-visible buttons on every row: no hover tricks, but cluttered
  and noisy on the list page (revisiting this decision: the icon was
  always-visible on /show and hover-reveal on list rows; a later
  follow-up made the show page default always-visible and the icon
  U+29C9).
- Click the row itself to copy: no visible affordance, surprising.

Consequences:
- webui.js grows (~5KB -> ~6KB); still first-party, no new vendor asset.
- The server markup gains a small copy button per row (no-JS users see
  the icon too; the JS only adds the click handler).
- Plain http:// LAN usage works via the execCommand fallback; last
  resort is a prompt showing the text for manual copy.
- Mobile/touch support deferred to tracker issue hash:0649b64e.
