/* webui.js - client-side markdown rendering for the issue tracker web UI.
 *
 * Progressive enhancement (ADR-0008): the server sends HTML-escaped <pre>
 * blocks as the no-JS fallback; this script upgrades each one to rendered
 * markdown. Vendored markdown-it 14.1.0 served from /static/.
 *
 * Policy (ADR-0008):
 *   - html: false  - all raw HTML (e.g. <hash>, <date> placeholders) is
 *     escaped, never rendered as markup.
 *   - linkify: false - no autolink detection.
 *   - links: http/https/mailto schemes only; anything else renders as
 *     plain text.
 */
(function () {
  'use strict';

  function renderMarkdown() {
    var MarkdownIt = window.markdownit;
    if (!MarkdownIt) {
      return; // fallback: server-sent escaped <pre> blocks remain
    }
    var md = MarkdownIt({html: false, linkify: false, breaks: false});
    // ADR-0008: override the default validateLink (which also allows ftp:,
    // data:, and file:). Only http/https/mailto are allowed; anything else
    // is not a link token and renders as escaped plain text.
    md.validateLink = function (url) {
      var str = url.trim().toLowerCase();
      return str.indexOf('http:') === 0 ||
             str.indexOf('https:') === 0 ||
             str.indexOf('mailto:') === 0;
    };
    var blocks = document.querySelectorAll('pre.md');
    for (var i = 0; i < blocks.length; i++) {
      var el = blocks[i];
      var div = document.createElement('div');
      div.className = 'md';
      div.innerHTML = md.render(el.textContent);
      el.parentNode.replaceChild(div, el);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderMarkdown);
  } else {
    renderMarkdown();
  }
}());
