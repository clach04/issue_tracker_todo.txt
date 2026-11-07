# -*- coding: utf-8 -*-
"""
Standard Library Unit Test Suite for Local Issue Tracker (todo.py)
Compatible with Python 2.7+ and Python 3.x using only unittest and tempfile.
"""
from __future__ import print_function, unicode_literals

import os
import sys
import io
import shutil
import tempfile
import argparse
import unittest
import datetime

import todo

def _ns(**kw):
    # Construct command args with verbose OFF by default (quiet tests).
    kw.setdefault('verbose', False)
    return argparse.Namespace(**kw)

def _capture_stderr():
    if sys.version_info[0] >= 3:
        return io.StringIO()
    return _Py2TextBuffer()

class _Py2TextBuffer(object):
    # py2: print() feeds unicode into sys.stdout; io.BytesIO rejects
    # unicode ('unicode' does not have the buffer interface), so wrap it
    # and encode utf-8 on the way in.
    def __init__(self):
        self._buf = io.BytesIO()

    def write(self, s):
        if isinstance(s, unicode):
            s = s.encode('utf-8')
        self._buf.write(s)

    def flush(self):
        self._buf.flush()

    def getvalue(self):
        return self._buf.getvalue().decode('utf-8')

def _capture_stdout():
    if sys.version_info[0] >= 3:
        return io.StringIO()
    return _Py2TextBuffer()

def _as_text(buf):
    v = buf.getvalue()
    if isinstance(v, bytes):
        return v.decode('utf-8')
    return v

class TestLocalIssueTracker(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        # Silence all command output by default (the "noisy tests" fix).
        # Tests that assert on output do their own capture on top of this
        # and restore to these buffers afterwards.
        self._old_out, self._old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _capture_stdout(), _capture_stderr()

    def tearDown(self):
        sys.stdout, sys.stderr = self._old_out, self._old_err
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)

    def _extract_hash_from_todo(self):
        with open(todo.TODO_FILE, 'r') as f:
            line = f.readline().strip()
        for part in line.split():
            if part.startswith("hash:"):
                return part.split(":")[1]
        return None

    def _read(self, path):
        with open(path, 'r') as f:
            return f.read()

    def _add(self, title, **kw):
        args = _ns(title=title, description=kw.get('description'),
                   priority=kw.get('priority'), project=kw.get('project'),
                   context=kw.get('context'))
        # Keep test output quiet: cmd_add prints "Created issue ...".
        old_out = sys.stdout
        sys.stdout = _capture_stdout()
        try:
            todo.cmd_add(args)
        finally:
            sys.stdout = old_out
        return self._extract_hash_from_todo()

    def test_add_issue(self):
        todo.cmd_add(_ns(title="Fix critical login bug",
                         description="Users receive a 500 error on OAuth callback.",
                         priority="A", project="backend", context="auth"))

        content = self._read(todo.TODO_FILE)
        self.assertIn("Fix critical login bug", content)
        self.assertIn("(A)", content)
        self.assertIn("hash:", content)
        self.assertIn("+backend", content)
        self.assertIn("@auth", content)

        issue_hash = self._extract_hash_from_todo()
        self.assertIsNotNone(issue_hash)

        issue_dir = os.path.join(todo.ISSUES_DIR, issue_hash)
        self.assertTrue(os.path.isdir(issue_dir))
        self.assertTrue(os.path.isdir(os.path.join(issue_dir, 'comments')))
        self.assertTrue(os.path.isdir(os.path.join(issue_dir, 'attachments')))

        issue_md_path = os.path.join(issue_dir, 'issue.md')
        self.assertTrue(os.path.exists(issue_md_path))
        self.assertIn("Users receive a 500 error", self._read(issue_md_path))

    def test_comment_issue(self):
        issue_hash = self._add("Refactor database connection pool", priority="B")

        todo.cmd_comment(_ns(identifier=issue_hash,
                             text="Investigated connection limits; bumping pool size to 20."))

        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        comment_files = os.listdir(comments_dir)
        self.assertEqual(len(comment_files), 1)
        # Seconds-precision UTC timestamp format YYYYMMDD_HHMMSS.md
        name = comment_files[0]
        self.assertTrue(name.endswith(".md"))
        self.assertEqual(len(name), len("20261106_213000.md"))
        datetime.datetime.strptime(name[:-3], '%Y%m%d_%H%M%S')

        body = self._read(os.path.join(comments_dir, name))
        self.assertIn("bumping pool size to 20", body)

    def test_close_issue(self):
        issue_hash = self._add("Update documentation for API endpoints",
                               description="Needs OpenAPI 3.0 spec update.")

        todo.cmd_close(_ns(identifier=issue_hash))

        todo_content = self._read(todo.TODO_FILE)
        self.assertNotIn(issue_hash, todo_content)

        done_content = self._read(todo.DONE_FILE)
        self.assertIn(issue_hash, done_content)
        self.assertTrue(done_content.startswith("x "))

    def test_ambiguous_hash_prefix(self):
        self._add("First issue")
        self._add("Second issue")

        show_args = _ns(identifier="nonexistent")
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_show(show_args)
        finally:
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)
        # Expected-error stderr is captured AND asserted (noise -> check).
        out = _as_text(stderr)
        self.assertIn("No issue found", out)

    # ------------------------------------------------------------------
    # Identifier resolution
    # ------------------------------------------------------------------

    def test_resolve_by_line_number(self):
        h1 = self._add("Alpha issue")
        h2 = self._add("Beta issue")
        # cmd_add prepends; Beta is line 1, Alpha is line 2.
        self.assertEqual(todo.resolve_identifier(_ns(identifier="1", verbose=False), "1"), h2)
        self.assertEqual(todo.resolve_identifier(_ns(identifier="2", verbose=False), "2"), h1)

    def test_resolve_line_number_out_of_range_errors(self):
        self._add("Only issue")
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.resolve_identifier(_ns(identifier="99", verbose=False), "99")
        finally:
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)
        out = _as_text(stderr)
        self.assertIn("no line 99", out)
        self.assertIn("hash:<hex>", out)  # hint present, no hash fall-through

    def test_resolve_explicit_hash_prefix(self):
        self._add("Unique issue title")
        h = self._extract_hash_from_todo()
        resolved = todo.resolve_identifier(_ns(identifier="hash:" + h[:4], verbose=False),
                                           "hash:" + h[:4])
        self.assertEqual(resolved, h)

    def test_resolve_hex_token_prefers_hash(self):
        self._add("abc title")  # title substring 'abc...' may also exist
        h = self._extract_hash_from_todo()
        # Bare token must be hex-LIKE but not all-digits (all-digits
        # always means line number). Take the shortest prefix that
        # contains a non-decimal hex char; fall back to the full hash.
        prefix = h[:4]
        while not any(c in 'abcdef' for c in prefix) and len(prefix) < len(h):
            prefix = h[:len(prefix) + 1]
        if not any(c in 'abcdef' for c in prefix):
            prefix = h  # astronomically unlikely: full hash all digits
        resolved = todo.resolve_identifier(_ns(identifier=prefix, verbose=False), prefix)
        self.assertEqual(resolved, h)

    def test_resolve_title_substring(self):
        self._add("Fix the login redirection bug")
        resolved = todo.resolve_identifier(_ns(identifier="login redirection", verbose=False),
                                           "login redirection")
        self.assertEqual(resolved, self._extract_hash_from_todo())

    def test_resolve_title_substring_case_insensitive(self):
        self._add("Fix The LOGIN Redirection Bug")
        resolved = todo.resolve_identifier(_ns(identifier="login redirection", verbose=False),
                                           "login redirection")
        self.assertEqual(resolved, self._extract_hash_from_todo())

    def test_resolve_ambiguous_title_lists_matches(self):
        self._add("Fix login bug")
        self._add("Fix login page")
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.resolve_identifier(_ns(identifier="login", verbose=False), "login")
        finally:
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)
        out = _as_text(stderr)
        self.assertIn("Ambiguous identifier", out)
        self.assertIn("title matches:", out)
        self.assertIn("Fix login bug", out)
        self.assertIn("Fix login page", out)
        self.assertIn("hash:", out)  # both hashes listed with titles

    def test_resolve_digit_only_title_unreachable_bare(self):
        self._add("12345")
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.resolve_identifier(_ns(identifier="12345", verbose=False), "12345")
        finally:
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)  # line 12345 doesn't exist

        # Reachable via explicit hash form.
        h = self._extract_hash_from_todo()
        resolved = todo.resolve_identifier(_ns(identifier="hash:" + h, verbose=False),
                                           "hash:" + h)
        self.assertEqual(resolved, h)

    def test_resolve_hex_wins_over_title_prints_note(self):
        # Deterministic fixture: a hash dir 'deadbeef' plus a todo.txt line
        # whose title also contains 'dead'. Bare hex token 'dead' must
        # resolve via hash and print the note ALWAYS (not just --verbose).
        todo.ensure_environment()
        os.makedirs(os.path.join(todo.ISSUES_DIR, 'deadbeef'))
        with open(todo.TODO_FILE, 'w') as f:
            f.write("2026-11-06 deadbeef placeholder hash:deadbeef\n")
        out = _capture_stdout()
        old_out = sys.stdout
        sys.stdout = out
        try:
            resolved = todo.resolve_identifier(_ns(identifier="dead", verbose=False), "dead")
        finally:
            sys.stdout = old_out
        self.assertEqual(resolved, "deadbeef")
        self.assertIn("resolved via hash", out.getvalue())

    def test_resolve_blank_line_numbering_matches_list(self):
        # list numbers ALL lines including blanks; resolver must agree.
        h = self._add("Issue after blank")
        with open(todo.TODO_FILE, 'a') as f:
            f.write("\n")  # trailing blank line occupies line 2
        self._add("Second issue")  # prepended: now line 1, blank is line 2
        lines = self._read(todo.TODO_FILE).splitlines(True)
        self.assertEqual(len(lines), 3)
        # Second add prepends: line 1 = "Second issue", line 2 =
        # "Issue after blank", line 3 = the blank line (numbered by list).
        self.assertIn("Issue after blank", lines[1])
        self.assertEqual(lines[2].strip(), "")
        resolved = todo.resolve_identifier(_ns(identifier="2", verbose=False), "2")
        self.assertEqual(resolved, h)

    # ------------------------------------------------------------------
    # Editor chain
    # ------------------------------------------------------------------

    def test_find_editor_prefers_env(self):
        old = os.environ.get('EDITOR')
        os.environ['EDITOR'] = 'myeditor'
        try:
            self.assertEqual(todo._find_editor(), 'myeditor')
        finally:
            if old is None:
                del os.environ['EDITOR']
            else:
                os.environ['EDITOR'] = old

    def test_find_editor_falls_back_to_visual(self):
        old_e, old_v = os.environ.get('EDITOR'), os.environ.get('VISUAL')
        os.environ.pop('EDITOR', None)
        os.environ['VISUAL'] = 'visual_editor'
        try:
            self.assertEqual(todo._find_editor(), 'visual_editor')
        finally:
            if old_e is not None:
                os.environ['EDITOR'] = old_e
            if old_v is None:
                os.environ.pop('VISUAL', None)
            else:
                os.environ['VISUAL'] = old_v

    def test_find_editor_none_fails_loudly(self):
        # Simulate no env vars and no editors on PATH by pointing PATH at
        # an empty dir and clearing env.
        old_e, old_v, old_path = (os.environ.get('EDITOR'),
                                  os.environ.get('VISUAL'),
                                  os.environ.get('PATH'))
        os.environ.pop('EDITOR', None)
        os.environ.pop('VISUAL', None)
        os.environ['PATH'] = self.test_dir  # empty dir: no editors found
        try:
            result = todo._find_editor()
        finally:
            if old_e is not None:
                os.environ['EDITOR'] = old_e
            if old_v is not None:
                os.environ['VISUAL'] = old_v
            os.environ['PATH'] = old_path
        if os.name == 'nt':
            # On Windows notepad may still resolve if it's on the cleared
            # PATH; it is not (empty dir), so None is expected.
            self.assertIsNone(result)
        else:
            self.assertIsNone(result)

    def test_edit_uses_found_editor(self):
        self._add("Editable issue")
        h = self._extract_hash_from_todo()
        # Use sys.executable as a "fake editor" that exists everywhere.
        calls = []

        def fake_call(cmd):
            calls.append(cmd)
            return 0

        old_call = todo.subprocess.call
        old_find = todo._find_editor
        todo.subprocess.call = fake_call
        todo._find_editor = lambda: 'fake_editor'
        try:
            todo.cmd_edit(_ns(identifier=h, verbose=False))
        finally:
            todo.subprocess.call = old_call
            todo._find_editor = old_find
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'fake_editor')
        self.assertTrue(calls[0][1].endswith('issue.md'))

    def test_edit_no_editor_errors(self):
        self._add("Issue without editor")
        h = self._extract_hash_from_todo()
        old_find = todo._find_editor
        todo._find_editor = lambda: None
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_edit(_ns(identifier=h, verbose=False))
        finally:
            todo._find_editor = old_find
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)
        self.assertIn("no editor found", _as_text(stderr))

    # ------------------------------------------------------------------
    # list --closed
    # ------------------------------------------------------------------

    def test_list_closed(self):
        h = self._add("Closable issue")
        todo.cmd_close(_ns(identifier=h))
        # cmd_list prints; capture stdout and check done.txt line appears.
        captured = _capture_stderr()
        out = _capture_stdout()
        old_out = sys.stdout
        sys.stdout = out
        try:
            todo.cmd_list(_ns(closed=True, priority=None))
        finally:
            sys.stdout = old_out
        text = _as_text(out)
        self.assertIn("Closed", text)
        self.assertIn(h, text)
        self.assertIn("Closable issue", text)

    # ------------------------------------------------------------------
    # Close-on-closed remains an error
    # ------------------------------------------------------------------

    def test_close_twice_errors(self):
        h = self._add("Once only")
        todo.cmd_close(_ns(identifier=h))
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_close(_ns(identifier=h))
        finally:
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)
        self.assertIn("might already be closed", _as_text(stderr))

if __name__ == '__main__':
    unittest.main()
