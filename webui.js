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

  /* ADR-0010: custom todo.txt/done.txt grammar (part 2 of hash:0a7d7e68).
   * Token set: priority (A)/(B)/(C) traffic-light, completion date, x
   * completion mark (done.txt), hash: token (special color), generic
   * key:value, +project, @context, bare URLs. Order matters: URL before
   * key:value (https: would match), hash: before key:value.
   */
  function registerTodotxt(hljs) {
    var URL = {className: 'todo-url', begin: /https?:\/\/[^\s)]+/};
    var HASH = {className: 'todo-hash', begin: /\bhash:[0-9a-f]{8}\b/};
    var DATE = {className: 'todo-date', begin: /\b\d{4}-\d{2}-\d{2}\b/};
    var PROJECT = {className: 'todo-project', begin: /\B\+[a-z0-9_-]+/};
    var CONTEXT = {className: 'todo-context', begin: /\B@[a-z0-9_-]+/};
    var KEYVAL = {className: 'todo-keyval',
                  begin: /\b[a-z][a-z0-9_-]*:[a-z0-9][^\s]*/i};
    return {
      name: 'todo.txt',
      contains: [
        {className: 'todo-x', begin: /^x\s/, relevance: 0},
        {className: 'todo-pri-a', begin: /\(A\)/, relevance: 0},
        {className: 'todo-pri-b', begin: /\(B\)/, relevance: 0},
        {className: 'todo-pri-c', begin: /\(C\)/, relevance: 0},
        URL,
        HASH,
        DATE,
        PROJECT,
        CONTEXT,
        KEYVAL
      ]
    };
  }

  function renderTodotxt() {
    if (!window.hljs) {
      return; // fallback: server-sent escaped text stays
    }
    if (window.hljs.getLanguage('todotxt') === undefined) {
      window.hljs.registerLanguage('todotxt', registerTodotxt);
    }
    var spans = document.querySelectorAll('span.todotxt');
    for (var i = 0; i < spans.length; i++) {
      var el = spans[i];
      el.innerHTML = window.hljs.highlight(el.textContent,
                                           {language: 'todotxt'}).value;
    }
  }

  function renderMarkdown() {
    var MarkdownIt = window.markdownit;
    if (!MarkdownIt) {
      return; // fallback: server-sent escaped <pre> blocks remain
    }
    var md = MarkdownIt({
      html: false,
      linkify: false,
      breaks: false,
      // ADR-0009: highlight tagged code fences via vendored highlight.js.
      // Known language -> highlighted HTML (markdown-it wraps it verbatim).
      // Unknown or missing language -> empty string, markdown-it escapes
      // the code as plain text. No autodetection.
      highlight: function (code, lang) {
        if (window.hljs && lang && window.hljs.getLanguage(lang)) {
          return window.hljs.highlight(code, {language: lang}).value;
        }
        return '';
      }
    });
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

  /* ADR-0011: copy-to-clipboard. Copied text is the hash: token from
   * the button's data-copy attribute. Chain: navigator.clipboard
   * (secure contexts only), then hidden textarea + execCommand('copy')
   * (plain http:// LAN origins), then window.prompt as last resort.
   * Feedback: button text changes to 'copied' for ~1s.
   */
  function copyText(text, done) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        done(true);
      }, function () {
        copyViaExecCommand(text, done);
      });
      return;
    }
    copyViaExecCommand(text, done);
  }

  function copyViaExecCommand(text, done) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(ta);
    if (!ok) {
      window.prompt('Copy the hash token:', text);
    }
    done(ok);
  }

  function addCopyButtons() {
    var buttons = document.querySelectorAll('.copy-btn');
    var ICON = '\u29C9'; // copy icon (&#x29C9;)
    for (var i = 0; i < buttons.length; i++) {
      var btn = buttons[i];
      btn.addEventListener('click', function (event) {
        var self = event.currentTarget;
        var text = self.getAttribute('data-copy');
        if (!text) {
          return;
        }
        copyText(text, function (ok) {
          self.textContent = ok ? '\u2705' : '\u274C'; // check / cross
          self.className = 'copy-btn' + (ok ? ' copied' : '');
          setTimeout(function () {
            self.textContent = ICON;
            self.className = 'copy-btn';
          }, 1000);
        });
      });
    }
  }

  function renderAll() {
    renderTodotxt();
    renderMarkdown();
    addCopyButtons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderAll);
  } else {
    renderAll();
  }
}());
