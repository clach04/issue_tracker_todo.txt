#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Read-only web UI for the local issue tracker (todo.py).

Stdlib-only, Python 2.7 + Python 3 compatible. Server backend: anywsgi
first (if installed), stdlib wsgiref fallback (ADR-0007).

Routes (read-only v1, docs/plans/webui.md):
  /                                 - list open issues from todo.txt
  /show/<hash>                      - show page (prefix allowed)
  /show?line=<n>                    - show by todo.txt Index line (open only)
  /show/<hash>/attachments/<name>   - serve attachment bytes
"""
from __future__ import print_function, unicode_literals

import argparse
import glob
import io
import os
import re
import sys
import traceback

import todo

try:
    from urllib.parse import unquote
except ImportError:
    from urllib import unquote

try:
    import anywsgi
    from anywsgi import DEFAULT_LISTEN_ADDRESS, DEFAULT_SERVER_PORT
except ImportError:
    anywsgi = None
    DEFAULT_LISTEN_ADDRESS = '127.0.0.1'
    DEFAULT_SERVER_PORT = 8000

try:
    from urllib.parse import parse_qs
except ImportError:
    from urlparse import parse_qs

try:
    from html import escape as _html_escape
except ImportError:
    from cgi import escape as _cgi_escape
    def _html_escape(s):
        return _cgi_escape(s, quote=True)

TEXT_HTML = 'text/html; charset=utf-8'
OCTET_STREAM = 'application/octet-stream'

PAGE_STYLE = (
    '<style>'
    'body { font-family: monospace; margin: 1.5em; }'
    'table { border-collapse: collapse; }'
    'td, th { border: 1px solid #999; padding: 2px 8px; text-align: left; }'
    'pre { background: #f4f4f4; border: 1px solid #ccc; padding: 0.5em; '
    'white-space: pre-wrap; }'
    '.badge { color: #fff; background: #a00; padding: 0 6px; }'
    '.footer { font-size: 0.75em; margin-top: 2em; }'
    '</style>'
)

SHOW_RE = re.compile(r'^/show/([^/]+)(?:/attachments/(.+))?$')

# TODO: deferred markdown rendering - issue.md and comment bodies are
# rendered as HTML-escaped plain text in a <pre> block. A minimal
# stdlib markdown converter (or client-side renderer) is deferred; see
# tracker issue e072da96 (docs/plans/webui.md).


FOOTER_BANNER = (
    '<div class="footer"><a href="https://github.com/clach04/issue_tracker_todo.txt"'
    '>issue_tracker_todo.txt</a></div>'
)


def _page(title, body):
    return ('<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
            '<title>{}</title>'.format(_html_escape(title))
            + PAGE_STYLE
            + '</head><body>\n{}\n{}\n</body></html>'.format(
                body, FOOTER_BANNER))


def _respond(status, body, content_type=TEXT_HTML):
    if isinstance(body, type(u'')):
        body = body.encode('utf-8')
    return status, [('Content-Type', content_type),
                    ('Content-Length', str(len(body)))], body


def _error_page(status, detail):
    body = _page(status, '<h1>{}</h1><pre>{}</pre>'.format(
        _html_escape(status), _html_escape(detail)))
    return _respond(status, body)


def _read_text(path):
    # Display-only tolerance: utf-8 with errors='replace' so a stray
    # non-utf8 byte cannot blank the whole UI. The UI is read-only, so
    # this never corrupts data.
    with io.open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        return f.read()


def _read_text_lines(path):
    if not os.path.exists(path):
        return []
    with io.open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        return [l.rstrip('\r\n') for l in f]


def _index_page():
    todo_path = os.path.join(os.getcwd(), todo.TODO_FILE)
    lines = _read_text_lines(todo_path)
    rows = []
    # Blank lines count toward the Index number (matches cmd_list).
    for idx, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        h = todo._hash_of_line(line)
        if h:
            text = '<a href="/show/{}">{}</a>'.format(_html_escape(h),
                                                      _html_escape(line))
        else:
            # Unhashed Line: plain text, no link (read-only UI cannot mint).
            text = _html_escape(line)
        rows.append('<tr><td>{}</td><td>{}</td></tr>'.format(idx, text))
    body = ('<h1>Open Issues</h1>'
            '<table><tr><th>Line</th><th>Issue</th></tr>'
            + ''.join(rows) + '</table>')
    return _respond('200 OK', _page('Open Issues', body))


class _ResolverArgs(object):
    # resolve_identifier() only reads args.verbose.
    verbose = False


class _ResolutionError(Exception):
    def __init__(self, detail):
        Exception.__init__(self, detail)
        self.detail = detail


def _resolve(token):
    # resolve_identifier() reports failures via sys.exit(1) and prints
    # resolution notes to stdout; capture both streams and convert into
    # an HTTP 404.
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        return todo.resolve_identifier(_ResolverArgs(), token)
    except SystemExit:
        detail = sys.stderr.getvalue().strip()
        raise _ResolutionError(detail or
                               'No issue found matching token {!r}'.format(token))
    except EnvironmentError as e:
        # Missing todo.txt etc. (e.g. empty repo dir): no issues exist,
        # so 'no issue found' -> 404, not a 500. EnvironmentError covers
        # both py2 IOError and py3 OSError.
        raise _ResolutionError('No issue found matching token {!r}'.format(token))
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def _show_page(token, query):
    if 'line' in query:
        return _show_by_line(query['line'][0])
    if token is None:
        return _error_page('404 Not Found',
                           'No identifier given. Use /show/<hash> or '
                           '/show?line=<n>')
    return _show_by_identifier(token)


def _show_by_identifier(token):
    try:
        h = _resolve(token)
    except _ResolutionError as e:
        return _error_page('404 Not Found', e.detail)
    return _show_by_hash(h)


def _show_by_line(n):
    # Line-number show resolves against todo.txt only (open issues).
    if not todo.DIGITS_RE.match(n):
        return _error_page('404 Not Found',
                           'line number must be all digits: {!r}'.format(n))
    if not os.path.exists(os.path.join(os.getcwd(), todo.TODO_FILE)):
        return _error_page('404 Not Found',
                           'No {} in this directory'.format(todo.TODO_FILE))
    line = todo._in_range_line(n)
    if line is None:
        return _error_page('404 Not Found',
                           'line {} out of range in {}'.format(n, todo.TODO_FILE))
    h = todo._hash_of_line(line)
    if h:
        return _show_by_hash(h)
    # Unhashed Line: plain text, no hash to resolve.
    body = ('<h1>todo.txt line {}</h1><pre>{}</pre>'
            '<p><a href="/">back</a></p>'.format(n, _html_escape(line)))
    return _respond('200 OK', _page('todo.txt line {}'.format(n), body))


def _show_by_hash(h):
    index_line = todo.find_line_by_hash(todo.TODO_FILE, h)
    closed = False
    if index_line is None:
        index_line = todo.find_line_by_hash(todo.DONE_FILE, h)
        closed = index_line is not None
    if index_line is None:
        return _error_page('404 Not Found',
                           'No issue found for hash:{}'.format(h))
    title = todo._title_from_line(index_line)
    issue_dir = os.path.join(os.getcwd(), todo.ISSUES_DIR, h)
    parts = []
    badge = 'closed' if closed else 'open'
    parts.append('<h1>{} <span class="badge">{}</span></h1>'.format(
        _html_escape(title), badge))
    parts.append('<pre>Issue Hash : {}\nHash Token : hash:{}\n'
                 'Index Line : {}\n</pre>'.format(
                     _html_escape(h), _html_escape(h), _html_escape(index_line)))
    issue_md_path = os.path.join(issue_dir, 'issue.md')
    if os.path.exists(issue_md_path):
        parts.append('<h2>Description</h2>')
        parts.append('<pre>{}</pre>'.format(
            _html_escape(_read_text(issue_md_path).strip())))
    comments_dir = os.path.join(issue_dir, 'comments')
    if os.path.isdir(comments_dir):
        comment_files = sorted(glob.glob(os.path.join(comments_dir, '*.md')))
        if comment_files:
            parts.append('<h2>Comments</h2>')
            for cf in comment_files:
                c_name = os.path.splitext(os.path.basename(cf))[0]
                parts.append('<h3>[{}]</h3>'.format(_html_escape(c_name)))
                parts.append('<pre>{}</pre>'.format(
                    _html_escape(_read_text(cf).strip())))
    attachments_dir = os.path.join(issue_dir, 'attachments')
    if os.path.isdir(attachments_dir):
        attachments = sorted(os.listdir(attachments_dir))
        if attachments:
            parts.append('<h2>Attachments</h2><ul>')
            for att in attachments:
                parts.append('<li><a href="/show/{}/attachments/{}">{}</a>'
                             '</li>'.format(_html_escape(h), _html_escape(att),
                                            _html_escape(att)))
            parts.append('</ul>')
    parts.append('<p><a href="/">back</a></p>')
    return _respond('200 OK', _page(title, '\n'.join(parts)))


def _serve_attachment(token, name):
    # WSGI servers percent-decode PATH_INFO (and some WSGI tooling does
    # not), so decode the name here too: encoded '../' must behave the
    # same as a literal slash.
    name = unquote(name)
    try:
        h = _resolve(token)
    except _ResolutionError as e:
        return _error_page('404 Not Found', e.detail)
    base = os.path.realpath(os.path.join(os.getcwd(), todo.ISSUES_DIR, h,
                                         'attachments'))
    target = os.path.realpath(os.path.join(base, name))
    # Containment check BEFORE any existence check: a traversal path
    # must fail loudly as 'outside', not as 'not found'.
    if not os.path.isdir(base):
        return _error_page('404 Not Found',
                           'No attachments for hash:{}'.format(h))
    if not target.startswith(base + os.sep):
        return _error_page('404 Not Found',
                           'Attachment path outside attachments dir: {!r}'
                           .format(name))
    if not os.path.isfile(target):
        return _error_page('404 Not Found',
                           'Attachment not found: {!r}'.format(name))
    with open(target, 'rb') as f:
        data = f.read()
    return _respond('200 OK', data, OCTET_STREAM)


def _dispatch(environ):
    path = environ.get('PATH_INFO', '/')
    method = environ.get('REQUEST_METHOD', 'GET')
    if method not in ('GET', 'HEAD'):
        return _error_page('405 Method Not Allowed',
                           'method {} not supported; read-only UI, use GET'
                           .format(method))
    query = parse_qs(environ.get('QUERY_STRING', ''))
    if path == '/':
        return _index_page()
    if path == '/show':
        return _show_page(None, query)
    m = SHOW_RE.match(path)
    if m:
        token, att = m.group(1), m.group(2)
        if att:
            return _serve_attachment(token, att)
        return _show_page(token, query)
    return _error_page('404 Not Found', 'Unknown path: {!r}'.format(path))


def application(environ, start_response):
    try:
        status, headers, body = _dispatch(environ)
    except Exception:
        traceback.print_exc()
        status, headers, body = _error_page(
            '500 Internal Server Error',
            'Internal server error; see server stderr for the traceback.')
    # py2 wsgiref requires str (bytes) status/headers; unicode_literals
    # makes them unicode here. py3 str is unaffected.
    if sys.version_info[0] == 2:
        status = str(status)
        headers = [(str(k), str(v)) for k, v in headers]
    start_response(status, headers)
    return [body]


def main():
    parser = argparse.ArgumentParser(
        description='Read-only web UI for the local issue tracker (todo.py)')
    parser.add_argument('--listen-address', default=DEFAULT_LISTEN_ADDRESS,
                        help='Listen address (default {}); env LISTEN_ADDRESS '
                             'overrides'.format(DEFAULT_LISTEN_ADDRESS))
    parser.add_argument('--port', type=int, default=DEFAULT_SERVER_PORT,
                        help='Listen port (default {}); env LISTEN_PORT '
                             'overrides'.format(DEFAULT_SERVER_PORT))
    args = parser.parse_args()

    listen_address = os.environ.get('LISTEN_ADDRESS', args.listen_address)
    listen_port = os.environ.get('LISTEN_PORT', str(args.port))
    try:
        listen_port = int(listen_port)
    except ValueError:
        print('Error: LISTEN_PORT {!r} is not an integer'.format(listen_port),
              file=sys.stderr)
        sys.exit(1)

    print('Python %s on %s' % (sys.version, sys.platform))
    if anywsgi:
        anywsgi.my_start_server(application, listen_address=listen_address,
                                listen_port=listen_port)
    else:
        from wsgiref.simple_server import make_server
        print("Starting wsgiref HTTP server on http://%s:%d ..." % (listen_address, listen_port))
        httpd = make_server(listen_address, listen_port, application)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nServer stopped by user.')


if __name__ == '__main__':
    main()
