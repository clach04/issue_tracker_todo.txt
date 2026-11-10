# -*- coding: utf-8 -*-
"""
Test suite for todo_webui.py (read-only web UI).

Direct WSGI application calls with a fake environ (no sockets, py2+py3
deterministic), plus one smoke test of the wsgiref fallback handler.
"""
from __future__ import print_function, unicode_literals

import argparse
import os
import shutil
import sys
import tempfile
import unittest

import todo
import todo_webui


def _ns(**kw):
    # Construct command args with verbose OFF by default (quiet tests).
    kw.setdefault('verbose', False)
    return argparse.Namespace(**kw)


def _environ(path='/', method='GET', query=''):
    return {
        'REQUEST_METHOD': method,
        'PATH_INFO': path,
        'QUERY_STRING': query,
        'wsgi.url_scheme': 'http',
        'SERVER_NAME': '127.0.0.1',
        'SERVER_PORT': '8000',
    }


def _call(environ):
    """Run the WSGI app; return (status, headers, body_bytes)."""
    captured = {}

    def start_response(status, headers):
        captured['status'] = status
        captured['headers'] = dict(headers)

    body = todo_webui.application(environ, start_response)
    return captured['status'], captured['headers'], b''.join(body)


class TestWebUI(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)

    def _add(self, title, description=None):
        args = _ns(title=title, description=description,
                   priority=None, project=None, context=None)
        todo.cmd_add(args)
        with open(todo.TODO_FILE, 'r') as f:
            lines = [l.strip() for l in f if l.strip()]
        return todo._hash_of_line(lines[-1])

    def test_list_page_links_hashed_lines(self):
        self._add('first issue', description='hello')
        self._add('second issue')
        status, headers, body = _call(_environ('/'))
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['Content-Type'], 'text/html; charset=utf-8')
        text = body.decode('utf-8')
        self.assertIn('<a href="/show/', text)
        self.assertIn('first issue', text)
        self.assertIn('second issue', text)

    def test_footer_banner_on_every_page(self):
        # GitHub project link banner at the bottom of each page.
        self._add('an issue')
        for path in ('/', '/show/abc', '/show/abc/attachments/x',
                     '/nope', '/show?line=999'):
            status, headers, body = _call(_environ(path))
            text = body.decode('utf-8')
            self.assertIn(
                'href="https://github.com/clach04/issue_tracker_todo.txt"',
                text, 'footer missing on {}'.format(path))
            self.assertIn('class="footer"', text, 'footer missing on {}'.format(path))
            self.assertGreater(text.rindex('class="footer"'),
                               text.rindex('<h1>'),
                               'footer should be near bottom of page')

    def test_list_page_unhashed_line_plain_text(self):
        with open(todo.TODO_FILE, 'a') as f:
            f.write('hand written line without hash <a b>\n')
        status, headers, body = _call(_environ('/'))
        text = body.decode('utf-8')
        self.assertIn('hand written line without hash', text)
        # No link for the unhashed line; the HTML is escaped.
        self.assertNotIn('<a href="/show/', text)

    def test_show_page_renders_description_comments_attachments(self):
        h = self._add('shown issue', description='body text')
        todo.cmd_comment(_ns(identifier=h, text='a comment', verbose=False))
        att_dir = os.path.join(todo.ISSUES_DIR, h, 'attachments')
        os.makedirs(att_dir)
        with open(os.path.join(att_dir, 'log.txt'), 'wb') as f:
            f.write(b'\x00\x01binary')
        status, headers, body = _call(_environ('/show/' + h))
        self.assertEqual(status, '200 OK')
        text = body.decode('utf-8')
        self.assertIn('shown issue', text)
        self.assertIn('body text', text)
        self.assertIn('a comment', text)
        self.assertIn('log.txt', text)
        self.assertIn('hash:{}'.format(h), text)
        # Open issue: no closed badge.
        self.assertNotIn('class="badge">closed', text)

    def test_show_page_md_pre_tags_and_scripts(self):
        # Show pages tag markdown blocks for the bootstrap and reference the
        # vendored markdown-it + bootstrap (ADR-0008).
        h = self._add('md issue', description='**bold** text')
        todo.cmd_comment(_ns(identifier=h, text='plain comment', verbose=False))
        status, headers, body = _call(_environ('/show/' + h))
        self.assertEqual(status, '200 OK')
        text = body.decode('utf-8')
        self.assertIn('<pre class="md">**bold** text</pre>', text)
        self.assertIn('<pre class="md">plain comment</pre>', text)
        self.assertIn('src="/static/markdown-it-14.1.0.min.js"', text)
        self.assertIn('src="/static/highlight-11.9.0.min.js"', text)
        self.assertIn('src="/static/webui.js"', text)
        # Metadata block (hash/index line) is NOT markdown-rendered.
        self.assertIn('<pre>Issue Hash :', text)
        self.assertNotIn('<pre class="md">Issue Hash', text)

    def test_non_md_pages_have_no_scripts(self):
        # Error pages carry no assets; the index carries the todotxt set
        # (highlight.js + bootstrap, no markdown-it) per ADR-0010.
        self._add('an issue')
        status, headers, body = _call(_environ('/'))
        text = body.decode('utf-8')
        self.assertIn('src="/static/highlight-11.9.0.min.js"', text)
        self.assertIn('src="/static/webui.js"', text)
        self.assertNotIn('markdown-it', text)
        self.assertNotIn('<pre class="md"', text)
        for path in ('/show/abc', '/nope'):
            status, headers, body = _call(_environ(path))
            text = body.decode('utf-8')
            self.assertNotIn('<script', text, 'script on {}'.format(path))
            self.assertNotIn('<pre class="md"', text,
                             'md block on {}'.format(path))

    def test_index_highlights_todotxt_tokens(self):
        # List lines are wrapped in span.todotxt for the client-side
        # grammar (ADR-0010); hashed lines link to the show page.
        self._add('todo.txt line with (A) priority +proj @ctx')
        status, headers, body = _call(_environ('/'))
        self.assertEqual(status, '200 OK')
        text = body.decode('utf-8')
        self.assertIn('<span class="todotxt">', text)
        self.assertIn('(A)', text)
        self.assertIn('+proj', text)
        self.assertIn('@ctx', text)
        self.assertIn('.hljs-todo-pri-a', text)
        self.assertIn('.hljs-todo-hash', text)

    def test_index_done_section_collapsed(self):
        # done.txt is listed under a collapsed <details> with the same
        # grammar (ADR-0010).
        h = self._add('doomed issue')
        todo.cmd_close(_ns(identifier=h, verbose=False))
        status, headers, body = _call(_environ('/'))
        self.assertEqual(status, '200 OK')
        text = body.decode('utf-8')
        self.assertIn('<details><summary>Closed Issues (done.txt)</summary>', text)
        self.assertIn('<span class="todotxt">x 2026-', text)
        self.assertIn('doomed issue', text)
        done_part = text[text.rindex('Closed Issues'):]
        self.assertNotIn('href="/show/', done_part,
                         'done.txt lines should not be links')

    def test_index_done_section_absent_when_empty(self):
        # Fresh dir: no done.txt -> no details section.
        self._add('only issue')
        status, headers, body = _call(_environ('/'))
        self.assertEqual(status, '200 OK')
        text = body.decode('utf-8')
        self.assertNotIn('<details>', text)
        self.assertNotIn('Closed Issues', text)

    def test_static_serves_markdown_it_and_bootstrap(self):
        status, headers, body = _call(_environ('/static/webui.js'))
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['Content-Type'], 'text/javascript; charset=utf-8')
        self.assertIn('Cache-Control', headers)
        self.assertIn('markdown-it', body.decode('utf-8'))
        status, headers, body = _call(
            _environ('/static/markdown-it-14.1.0.min.js'))
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['Content-Type'], 'text/javascript; charset=utf-8')
        self.assertIn('Cache-Control', headers)
        self.assertGreater(len(body), 100000)  # vendored minified library

    def test_static_unknown_asset_404(self):
        # Only the known files are served; no user-controlled filenames.
        status, headers, body = _call(_environ('/static/nope.js'))
        self.assertEqual(status, '404 Not Found')
        status, headers, body = _call(
            _environ('/static/markdown-it-99.9.9.min.js'))
        self.assertEqual(status, '404 Not Found')
        status, headers, body = _call(
            _environ('/static/highlight-99.9.9.min.js'))
        self.assertEqual(status, '404 Not Found')
        # Traversal: regex only matches a single segment, so no '..' path.
        status, headers, body = _call(_environ('/static/..%2Ftodo.py'))
        self.assertEqual(status, '404 Not Found')

    def test_static_serves_highlight_js(self):
        status, headers, body = _call(
            _environ('/static/highlight-11.9.0.min.js'))
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['Content-Type'], 'text/javascript; charset=utf-8')
        self.assertIn('Cache-Control', headers)
        text = body.decode('utf-8')
        self.assertIn('Highlight.js', text)
        self.assertGreater(len(body), 100000)  # vendored minified library

    def test_show_page_has_token_styles(self):
        # Minimal highlight.js token colors are in the page style.
        h = self._add('style issue')
        status, headers, body = _call(_environ('/show/' + h))
        self.assertEqual(status, '200 OK')
        self.assertIn('.hljs-keyword', body.decode('utf-8'))

    def test_grammar_class_names_no_double_prefix(self):
        # highlight.js prepends its own classPrefix ("hljs-") to grammar
        # classNames, so grammar modes must use bare names (e.g. "todo-hash"
        # -> emitted as "hljs-todo-hash"). A grammar-level "hljs-" prefix
        # produced "hljs-hljs-todo-..." and styled nothing. Regression test.
        # webui.js lives next to todo_webui.py, not the test cwd.
        js_path = os.path.join(os.path.dirname(
            os.path.abspath(todo_webui.__file__)), 'webui.js')
        with open(js_path) as f:
            js = f.read()
        self.assertNotIn("className: 'hljs-", js,
                         'grammar class names must not carry the hljs- '
                         'prefix (highlight.js adds it)')
        self.assertIn("className: 'todo-hash'", js)
        # CSS must match the emitted names (hljs- + grammar name).
        self.assertIn('.hljs-todo-hash', todo_webui.PAGE_STYLE)

    def test_show_page_closed_badge(self):
        h = self._add('closing issue', description='will close')
        todo.cmd_close(_ns(identifier=h, verbose=False))
        status, headers, body = _call(_environ('/show/' + h))
        self.assertEqual(status, '200 OK')
        text = body.decode('utf-8')
        self.assertIn('closed', text)
        self.assertIn('will close', text)

    def test_show_page_prefix_resolution(self):
        h = self._add('prefix issue', description='x')
        status, headers, body = _call(_environ('/show/' + h[:4]))
        self.assertEqual(status, '200 OK')
        self.assertIn('prefix issue', body.decode('utf-8'))

    def test_show_page_ambiguous_prefix_404(self):
        h1 = self._add('alpha issue', description='x')
        h2 = self._add('bravo issue', description='x')
        # Find a shared prefix that is ambiguous between the two hashes.
        i = 0
        while i < min(len(h1), len(h2)) and h1[i] == h2[i]:
            i += 1
        if i == 0:
            self.skipTest('hashes share no common prefix (no ambiguity possible)')
        prefix = h1[:i]
        status, headers, body = _call(_environ('/show/' + prefix))
        self.assertEqual(status, '404 Not Found')
        self.assertIn('Ambiguous', body.decode('utf-8'))

    def test_show_page_unknown_hash_404(self):
        status, headers, body = _call(_environ('/show/zzzzzzzz'))
        self.assertEqual(status, '404 Not Found')
        self.assertIn('No issue found', body.decode('utf-8'))

    def test_show_by_line_number(self):
        h = self._add('line issue', description='x')
        status, headers, body = _call(_environ('/show', query='line=1'))
        self.assertEqual(status, '200 OK')
        self.assertIn('line issue', body.decode('utf-8'))

    def test_show_by_line_out_of_range_404(self):
        self._add('only issue', description='x')
        status, headers, body = _call(_environ('/show', query='line=99'))
        self.assertEqual(status, '404 Not Found')
        self.assertIn('out of range', body.decode('utf-8'))

    def test_show_by_line_rejects_non_digits(self):
        status, headers, body = _call(_environ('/show', query='line=abc'))
        self.assertEqual(status, '404 Not Found')
        self.assertIn('all digits', body.decode('utf-8'))

    def test_show_by_line_closed_issue_not_resolvable(self):
        h = self._add('closed line issue', description='x')
        todo.cmd_close(_ns(identifier=h, verbose=False))
        status, headers, body = _call(_environ('/show', query='line=1'))
        self.assertEqual(status, '404 Not Found')
        self.assertIn('out of range', body.decode('utf-8'))

    def test_attachment_serving_bytes(self):
        h = self._add('att issue', description='x')
        att_dir = os.path.join(todo.ISSUES_DIR, h, 'attachments')
        os.makedirs(att_dir)
        with open(os.path.join(att_dir, 'data.bin'), 'wb') as f:
            f.write(b'\x00\x01\x02')
        status, headers, body = _call(
            _environ('/show/{}/attachments/data.bin'.format(h)))
        self.assertEqual(status, '200 OK')
        self.assertEqual(headers['Content-Type'], 'application/octet-stream')
        self.assertEqual(body, b'\x00\x01\x02')

    def test_attachment_traversal_rejected(self):
        h = self._add('trav issue', description='x')
        att_dir = os.path.join(todo.ISSUES_DIR, h, 'attachments')
        os.makedirs(att_dir)
        with open(os.path.join(att_dir, 'ok.txt'), 'wb') as f:
            f.write(b'ok')
        for path in ('/show/{}/attachments/..%2F..%2Ftodo.txt'.format(h),
                     '/show/{}/attachments/../../todo.txt'.format(h)):
            status, headers, body = _call(_environ(path))
            self.assertEqual(status, '404 Not Found')
            self.assertIn('outside', body.decode('utf-8'))

    def test_attachment_missing_404(self):
        h = self._add('noatt issue', description='x')
        att_dir = os.path.join(todo.ISSUES_DIR, h, 'attachments')
        os.makedirs(att_dir)
        status, headers, body = _call(
            _environ('/show/{}/attachments/nope.txt'.format(h)))
        self.assertEqual(status, '404 Not Found')
        self.assertIn('nope.txt', body.decode('utf-8'))

    def test_attachment_no_attachments_dir_404(self):
        h = self._add('nodir issue', description='x')
        status, headers, body = _call(
            _environ('/show/{}/attachments/anything.txt'.format(h)))
        self.assertEqual(status, '404 Not Found')
        self.assertIn('No attachments for hash:{}'.format(h),
                      body.decode('utf-8'))

    def test_unknown_path_404(self):
        status, headers, body = _call(_environ('/nope'))
        self.assertEqual(status, '404 Not Found')
        self.assertIn('Unknown path', body.decode('utf-8'))

    def test_post_method_405(self):
        status, headers, body = _call(_environ('/', method='POST'))
        self.assertEqual(status, '405 Method Not Allowed')

    def test_show_escaped_html_no_injection(self):
        h = self._add('escape issue', description='<script>alert(1)</script>')
        status, headers, body = _call(_environ('/show/' + h))
        text = body.decode('utf-8')
        self.assertIn('&lt;script&gt;', text)
        self.assertNotIn('<script>', text)

    def test_wsgiref_fallback_smoke(self):
        # wsgiref fallback handler (ADR-0007): real server on a thread,
        # one socket request, then shut down. Skipped if binding is
        # unavailable (e.g. sandboxed network).
        from wsgiref.simple_server import make_server
        try:
            httpd = make_server('127.0.0.1', 0, todo_webui.application)
        except OSError:
            self.skipTest('cannot bind a socket in this environment')
        import threading
        t = threading.Thread(target=httpd.serve_forever)
        t.daemon = True
        t.start()
        try:
            port = httpd.server_address[1]
            try:
                from urllib.request import urlopen
            except ImportError:
                from urllib2 import urlopen
            response = urlopen('http://127.0.0.1:{}/'.format(port))
            page = response.read().decode('utf-8')
            # py2 addinfourl has no .status; getcode() works on both.
            self.assertEqual(response.getcode(), 200)
            self.assertIn('<h1>Open Issues</h1>', page)
        finally:
            httpd.shutdown()
            httpd.server_close()
            t.join()


if __name__ == '__main__':
    unittest.main()
