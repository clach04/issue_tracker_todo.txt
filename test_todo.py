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
import re

import todo
import md2todo

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
        # ADR-0004: `add` appends, so the newest issue is the LAST line.
        with open(todo.TODO_FILE, 'r') as f:
            lines = [l.strip() for l in f if l.strip()]
        line = lines[-1]
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
        # comments/ and attachments/ are created lazily, never at add time.
        self.assertFalse(os.path.exists(os.path.join(issue_dir, 'comments')))
        self.assertFalse(os.path.exists(os.path.join(issue_dir, 'attachments')))

        issue_md_path = os.path.join(issue_dir, 'issue.md')
        self.assertTrue(os.path.exists(issue_md_path))
        self.assertIn("Users receive a 500 error", self._read(issue_md_path))

    def test_add_without_description_creates_no_dir(self):
        issue_hash = self._add("Stub only issue")
        issue_dir = os.path.join(todo.ISSUES_DIR, issue_hash)
        self.assertFalse(os.path.exists(issue_dir))
        # Still resolvable and listable.
        self.assertEqual(todo.resolve_identifier(_ns(identifier="hash:"+issue_hash, verbose=False),
                                                 "hash:"+issue_hash), issue_hash)

    # add: append keeps Index line numbers stable for life (ADR-0004)
    # ------------------------------------------------------------------

    def _add_reported_line(self, title):
        # Run cmd_add quietly; return (hash, reported line number, out).
        out = _capture_stdout()
        old_out = sys.stdout
        sys.stdout = out
        try:
            todo.cmd_add(_ns(title=title, description=None, priority=None,
                             project=None, context=None))
        finally:
            sys.stdout = old_out
        text = _as_text(out)
        m = re.search(r"at line (\d+)", text)
        self.assertIsNotNone(m, "add must report the new line number: {!r}".format(text))
        return self._extract_hash_from_todo(), int(m.group(1)), text

    def test_add_appends_and_prints_line_number(self):
        h1, n1, out1 = self._add_reported_line("First issue")
        self.assertEqual(n1, 1, "first issue in an empty Index is line 1")
        self.assertIn("Created issue [{}] at line 1".format(h1), out1)
        self.assertIn("'First issue'", out1, "add keeps the title in its output")
        h2, n2, _out2 = self._add_reported_line("Second issue")
        self.assertEqual(n2, 2, "add appends: the second issue is line 2")
        lines = self._read_raw(todo.TODO_FILE).splitlines()
        self.assertIn(h1, lines[0], "the first issue stays on line 1")
        self.assertIn(h2, lines[1], "the new issue is appended at the end")

    def test_add_does_not_renumber_existing_issues(self):
        h1, n1, _out = self._add_reported_line("Alpha issue")
        h2, n2, _out = self._add_reported_line("Beta issue")
        h3, n3, _out = self._add_reported_line("Gamma issue")
        self.assertEqual([n1, n2, n3], [1, 2, 3])
        # The number captured BEFORE the later adds still resolves to the
        # same hash afterwards: stable for life (ADR-0004).
        for number, expected in ((1, h1), (2, h2), (3, h3)):
            resolved = todo.resolve_identifier(
                _ns(identifier=str(number), verbose=False), str(number))
            self.assertEqual(resolved, expected,
                             "line {} must still address the same issue".format(number))

    def test_add_appends_to_file_without_trailing_newline(self):
        # A hand-written last line with no trailing newline must not be
        # glued onto the appended line.
        self._write_raw(todo.TODO_FILE, "manual no newline hash:deadbeef")
        h, n, _out = self._add_reported_line("Appended issue")
        self.assertEqual(n, 2, "the unterminated line still occupies line 1")
        lines = self._read_raw(todo.TODO_FILE).splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].endswith("hash:deadbeef"), "line 1 untouched")
        self.assertIn(h, lines[1])

    # add: collision-guarded minting (ADR-0003)
    # ------------------------------------------------------------------

    def _add_capture(self, title, **kw):
        # Like _add, but returns (minted_hash, stderr_text, excinfo_code).
        args = _ns(title=title, description=kw.get('description'),
                   priority=kw.get('priority'), project=kw.get('project'),
                   context=kw.get('context'))
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _capture_stdout(), _capture_stderr()
        err = sys.stderr
        try:
            todo.cmd_add(args)
            code = 0
        except SystemExit as exc:
            code = exc.code
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        return _as_text(err), code

    def _add_with_fake_generate(self, title, seq):
        # Patch generate_hash to walk 'seq'; returns (stderr, code, calls).
        real_generate = todo.generate_hash
        calls = []

        def fake_generate(t):
            value = seq[min(len(calls), len(seq) - 1)]
            calls.append(value)
            return value

        todo.generate_hash = fake_generate
        try:
            err, code = self._add_capture(title)
        finally:
            todo.generate_hash = real_generate
        return err, code, calls

    def test_add_retries_on_hash_collision(self):
        todo.ensure_environment()
        # 'deadbeef' already taken in todo.txt; the collision must be
        # retried, not silently aliased.
        self._write_raw(todo.TODO_FILE, "2026-11-06 taken hash:deadbeef\n")
        err, code, calls = self._add_with_fake_generate(
            "Fresh issue", ['deadbeef', 'deadbeef', 'feedface'])
        self.assertEqual(code, 0, "unexpected failure: {!r}".format(err))
        self.assertEqual(len(calls), 3, "expected 2 collisions + 1 free mint")
        lines = self._read_raw(todo.TODO_FILE).splitlines()
        self.assertEqual(len(lines), 2, "expected exactly one added line")
        # ADR-0004: add appends: the fixture line is 1, the new one 2.
        self.assertEqual(todo._hash_of_line(lines[1]), "feedface",
                         "add must store the first unique candidate")
        self.assertEqual(todo._hash_of_line(lines[0]), "deadbeef",
                         "the existing line must be untouched")

    def test_add_retries_on_hash_collision_in_done_file(self):
        todo.ensure_environment()
        # done.txt counts too: a hash reused after closing must not alias.
        self._write_raw(todo.DONE_FILE, "x 2026-11-06 old hash:cafebabe\n")
        err, code, calls = self._add_with_fake_generate(
            "Fresh issue", ['cafebabe', 'beefcafe'])
        self.assertEqual(code, 0, "unexpected failure: {!r}".format(err))
        self.assertEqual(len(calls), 2, "done.txt hash was not treated as taken")
        line = self._read_raw(todo.TODO_FILE).splitlines()[0]
        self.assertEqual(todo._hash_of_line(line), "beefcafe")

    def test_add_fails_loudly_after_ten_collisions(self):
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE, "2026-11-06 taken hash:deadbeef\n")
        err, code, calls = self._add_with_fake_generate("Doomed issue", ['deadbeef'])
        self.assertEqual(code, 1, "add must fail loudly on persistent collision")
        self.assertEqual(len(calls), todo.MINT_ATTEMPTS)
        self.assertIn("could not mint a unique hash", err)
        # Fail fast: nothing was written and no orphan details dir exists.
        lines = self._read_raw(todo.TODO_FILE).splitlines()
        self.assertEqual(lines, ["2026-11-06 taken hash:deadbeef"])
        self.assertFalse(os.path.exists(os.path.join(todo.ISSUES_DIR, "deadbeef")),
                         "failed add must not leave a details directory")

    def test_comment_bootstraps_issue_dir(self):
        issue_hash = self._add("Lazy dir issue")
        self.assertFalse(os.path.exists(os.path.join(todo.ISSUES_DIR, issue_hash)))
        todo.cmd_comment(_ns(identifier="hash:"+issue_hash, text="bootstrap comment"))
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        self.assertEqual(os.listdir(comments_dir), [os.listdir(comments_dir)[0]])
        self.assertTrue(os.listdir(comments_dir)[0].endswith('.md'))

    def test_edit_bootstraps_issue_dir(self):
        self._add("Bootstrap edit issue")
        issue_hash = self._extract_hash_from_todo()
        self.assertFalse(os.path.exists(os.path.join(todo.ISSUES_DIR, issue_hash)))
        calls = []

        def fake_call(cmd):
            calls.append(cmd)
            return 0

        old_call = todo.subprocess.call
        todo.subprocess.call = fake_call
        try:
            todo.cmd_edit(_ns(identifier="hash:"+issue_hash, verbose=False))
        finally:
            todo.subprocess.call = old_call
        self.assertEqual(len(calls), 1)
        issue_md = calls[0][1]
        self.assertTrue(issue_md.endswith('issue.md'))
        body = self._read(issue_md)
        self.assertIn("Bootstrap edit issue", body)  # title stub written

    def test_comment_issue(self):
        issue_hash = self._add("Refactor database connection pool", priority="B")

        todo.cmd_comment(_ns(identifier="hash:"+issue_hash,
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

    # --- Dash Marker stdin support (docs/plans/comment-stdin.md) ---

    def _fake_stdin(self, data):
        # Replace sys.stdin with a fake piped stdin (isatty False).
        # data is bytes; None means an empty pipe. When py2_style=True the
        # fake mimics py2's file stdin (read() on the object itself, no
        # .buffer) so the read_stdin_bytes() shim is exercised on both
        # interpreters (hash:d2b6b1cf).
        import io
        buf = io.BytesIO(data if data is not None else b'')

        class _FakeStdin(object):
            def __init__(self, buffer, py2_style):
                self._buffer = buffer
                self._py2_style = py2_style
                if not py2_style:
                    self.buffer = buffer
            def read(self):
                assert self._py2_style, "read() only on py2-style fake stdin"
                return self._buffer.read()
            def isatty(self):
                return False
        self._old_stdin = sys.stdin
        sys.stdin = _FakeStdin(buf, py2_style=(sys.version_info[0] < 3))
        return buf

    def _restore_stdin(self):
        sys.stdin = self._old_stdin

    def test_comment_dash_marker_reads_stdin(self):
        issue_hash = self._add("Stdin comment issue")
        self._fake_stdin(b'piped body line one\nline two\n')
        try:
            todo.cmd_comment(_ns(identifier="hash:"+issue_hash, text="-"))
        finally:
            self._restore_stdin()
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        comment_files = os.listdir(comments_dir)
        self.assertEqual(len(comment_files), 1)
        # Raw bytes written as-is: no added newline, no normalization.
        body = self._read(os.path.join(comments_dir, comment_files[0]))
        self.assertEqual(body, 'piped body line one\nline two\n')

    def test_comment_stdin_binary_bytes_py2_style(self):
        # hash:d2b6b1cf: py2 stdin is a file object (read() returns raw
        # bytes, no .buffer attribute). The fake py2-style stdin plus a
        # non-ascii/high-byte body prove read_stdin_bytes() is
        # byte-faithful on BOTH interpreters - the pre-fix code crashed
        # with AttributeError on py2 here.
        issue_hash = self._add("Stdin py2 issue")
        raw = b'\x00\x01\xfe\xff binary \xc3\xa9 tail\n'
        self._fake_stdin(raw)
        try:
            todo.cmd_comment(_ns(identifier="hash:"+issue_hash, text="-"))
        finally:
            self._restore_stdin()
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        comment_files = os.listdir(comments_dir)
        self.assertEqual(len(comment_files), 1)
        with open(os.path.join(comments_dir, comment_files[0]), 'rb') as f:
            self.assertEqual(f.read(), raw)

    def test_comment_extra_text_arguments_fail_loudly(self):
        # hash:d2b6b1cf case 2: `cat f` word-split into several tokens
        # used to die in argparse with a bare usage error. With
        # nargs='+' cmd_comment now rejects extras with a hint naming
        # the deferred join idea (hash:6e4084b4).
        issue_hash = self._add("Extra args issue")
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(AssertionError) as excinfo:
                todo.cmd_comment(_ns(identifier="hash:"+issue_hash,
                                     text=["test", "line2"]))
        finally:
            sys.stderr = old_stderr
        self.assertIn("one text argument", str(excinfo.exception))
        self.assertIn("hash:6e4084b4", str(excinfo.exception))
        # No comment file created on failure.
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        self.assertFalse(os.path.exists(comments_dir))

    def test_comment_dash_marker_conflict_with_text_arg_fails(self):
        issue_hash = self._add("Stdin conflict issue")
        self._fake_stdin(b'piped body\n')
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_comment(_ns(identifier="hash:"+issue_hash,
                                     text="inline text"))
        finally:
            sys.stderr = old_stderr
            self._restore_stdin()
        self.assertEqual(excinfo.exception.code, 1)
        out = _as_text(stderr)
        self.assertIn("both a text argument", out)
        self.assertIn("piped stdin", out)
        # No comment file created on failure.
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        self.assertFalse(os.path.exists(comments_dir))

    def test_comment_dash_marker_empty_stdin_fails(self):
        issue_hash = self._add("Stdin empty issue")
        self._fake_stdin(b'')
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_comment(_ns(identifier="hash:"+issue_hash, text="-"))
        finally:
            sys.stderr = old_stderr
            self._restore_stdin()
        self.assertEqual(excinfo.exception.code, 1)
        out = _as_text(stderr)
        self.assertIn("no stdin content", out)
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        self.assertFalse(os.path.exists(comments_dir))

    def test_comment_dash_marker_tty_stdin_fails(self):
        issue_hash = self._add("Stdin tty issue")

        class _TtyStdin(object):
            def __init__(self, fallback):
                self.buffer = fallback
            def isatty(self):
                return True
        self._old_stdin = sys.stdin
        # buffer points at an empty pipe so any read() is empty too.
        import io
        sys.stdin = _TtyStdin(io.BytesIO(b''))
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_comment(_ns(identifier="hash:"+issue_hash, text="-"))
        finally:
            sys.stderr = old_stderr
            sys.stdin = self._old_stdin
        self.assertEqual(excinfo.exception.code, 1)
        out = _as_text(stderr)
        self.assertIn("stdin is a terminal", out)
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        self.assertFalse(os.path.exists(comments_dir))

    def test_comment_text_arg_with_piped_stdin_conflicts(self):
        # The settled conflict rule: ANY text arg plus piped stdin is a
        # loud error, not just the dash marker.
        issue_hash = self._add("Stdin text conflict issue")
        self._fake_stdin(b'piped body\n')
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_comment(_ns(identifier="hash:"+issue_hash,
                                     text="inline text"))
        finally:
            sys.stderr = old_stderr
            self._restore_stdin()
        self.assertEqual(excinfo.exception.code, 1)
        out = _as_text(stderr)
        self.assertIn("both a text argument", out)
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        self.assertFalse(os.path.exists(comments_dir))

    def test_comment_binary_stdin_bytes(self):
        # Byte fidelity: non-UTF8 bytes pass through untouched.
        issue_hash = self._add("Stdin binary issue")
        raw = b'\xff\xfe binary-ish bytes \x00\x01\n'
        self._fake_stdin(raw)
        try:
            todo.cmd_comment(_ns(identifier="hash:"+issue_hash, text="-"))
        finally:
            self._restore_stdin()
        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        name = os.listdir(comments_dir)[0]
        with open(os.path.join(comments_dir, name), 'rb') as f:
            self.assertEqual(f.read(), raw)

    def test_close_issue(self):
        issue_hash = self._add("Update documentation for API endpoints",
                               description="Needs OpenAPI 3.0 spec update.")

        todo.cmd_close(_ns(identifier="hash:"+issue_hash))

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

    # show: explicit hash token for copy/paste
    # ------------------------------------------------------------------

    def _show(self, identifier):
        # Run cmd_show with stdout captured; return its text.
        out = _capture_stdout()
        old_out = sys.stdout
        sys.stdout = out
        try:
            todo.cmd_show(_ns(identifier=identifier))
        finally:
            sys.stdout = old_out
        return _as_text(out)

    def test_show_prints_pasteable_hash_token(self):
        issue_hash = self._add("Paste me", description="Body.")
        out = self._show("hash:" + issue_hash)
        token = "hash:" + issue_hash
        self.assertIn("Issue Hash : {}".format(issue_hash), out)
        self.assertIn("Hash Token : {}".format(token), out)
        # The printed token must round-trip through the resolver as-is.
        self.assertEqual(
            todo.resolve_identifier(_ns(identifier=token, verbose=False), token),
            issue_hash)

    def test_show_prints_pasteable_hash_token_for_digit_only_hash(self):
        # ~1 in 43 hashes are all decimal digits; the bare value would be
        # read as a line number, so the explicit form is what makes it
        # pasteable (ADR-0002).
        err, code, _calls = self._add_with_fake_generate("Digits", ['12345678'])
        self.assertEqual(code, 0, "unexpected failure: {!r}".format(err))
        out = self._show("hash:12345678")
        self.assertIn("Hash Token : hash:12345678", out)
        self.assertEqual(
            todo.resolve_identifier(_ns(identifier="hash:12345678", verbose=False),
                                    "hash:12345678"), "12345678")

    # ------------------------------------------------------------------
    # Identifier resolution
    # ------------------------------------------------------------------

    def test_resolve_by_line_number(self):
        h1 = self._add("Alpha issue")
        h2 = self._add("Beta issue")
        # cmd_add appends (ADR-0004); Alpha is line 1, Beta is line 2.
        self.assertEqual(todo.resolve_identifier(_ns(identifier="1", verbose=False), "1"), h1)
        self.assertEqual(todo.resolve_identifier(_ns(identifier="2", verbose=False), "2"), h2)

    def test_resolve_line_number_out_of_range_falls_through(self):
        # Out-of-range all-digit token: not a line number (todo.txt is
        # small), so fall through to hash then title (ADR-0002).
        self._add("Only issue")
        h = self._extract_hash_from_todo()
        if todo.HEX_RE.match(h):
            # Bare token only reaches the hash path when not all-digits;
            # the all-digits case is covered by the explicit-hash tests.
            self.assertEqual(todo.resolve_identifier(
                _ns(identifier="hash:" + h, verbose=False), "hash:" + h), h)
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
        self.assertIn("no issue found matching", out.lower())  # hash+title miss
        self.assertIn("hash prefix or title '99'", out)  # fell through both

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

    def test_resolve_digit_only_title_reachable_via_fallthrough(self):
        # Out-of-range all-digit token falls through to hash then title
        # (ADR-0002), so a digit-only title like '12345' is now reachable
        # by bare token when the line number is out of range.
        self._add("12345")
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.resolve_identifier(_ns(identifier="99", verbose=False), "99")
        finally:
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)  # no line 99, no hash, no title

        # Reachable via explicit hash form always.
        h = self._extract_hash_from_todo()
        resolved = todo.resolve_identifier(_ns(identifier="hash:" + h, verbose=False),
                                           "hash:" + h)
        self.assertEqual(resolved, h)

        # Reachable by bare token via the out-of-range fall-through.
        # '12345' is out of range (1 issue in todo.txt), so it resolves
        # as a hash prefix or title.
        bare = "12345" if todo.HEX_RE.match(h) else "99999"
        resolved = todo.resolve_identifier(_ns(identifier=bare, verbose=False), bare)
        self.assertEqual(resolved, h)
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
            f.write("\n")  # blank line now occupies line 2
        self._add("Second issue")  # appended: blank stays at line 2
        lines = self._read(todo.TODO_FILE).splitlines(True)
        self.assertEqual(len(lines), 3)
        # ADR-0004 (append): line 1 = "Issue after blank", line 2 = the
        # blank line (numbered by list), line 3 = "Second issue".
        self.assertIn("Issue after blank", lines[0])
        self.assertEqual(lines[1].strip(), "")
        self.assertIn("Second issue", lines[2])
        # The blank line does not shift the first issue off line 1.
        resolved = todo.resolve_identifier(_ns(identifier="1", verbose=False), "1")
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
            todo.cmd_edit(_ns(identifier="hash:"+h, verbose=False))
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
                todo.cmd_edit(_ns(identifier="hash:"+h, verbose=False))
        finally:
            todo._find_editor = old_find
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)
        self.assertIn("no editor found", _as_text(stderr))

    # edit: TODO_NO_EDITOR suppresses the editor launch (batch/CI)

    def _with_no_editor_env(self, value):
        # Set (or clear, when value is None) TODO_NO_EDITOR; returns the
        # previous value for restoration in a finally block.
        old = os.environ.get('TODO_NO_EDITOR')
        if value is None:
            os.environ.pop('TODO_NO_EDITOR', None)
        else:
            os.environ['TODO_NO_EDITOR'] = value
        return old

    def _restore_no_editor_env(self, old):
        os.environ.pop('TODO_NO_EDITOR', None)
        if old is not None:
            os.environ['TODO_NO_EDITOR'] = old

    def _edit_capturing_stderr(self, identifier):
        stderr = _capture_stderr()
        old_err = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_edit(_ns(identifier=identifier, verbose=False))
        finally:
            sys.stderr = old_err
        return excinfo.exception.code, _as_text(stderr)

    def test_edit_launch_disabled_by_env_fails_loudly(self):
        h = self._add("Batch issue")
        calls = []
        old_call, old_find = todo.subprocess.call, todo._find_editor
        todo.subprocess.call = lambda cmd: calls.append(cmd) or 0
        todo._find_editor = lambda: 'fake_editor'
        old_env = self._with_no_editor_env('1')
        try:
            code, err = self._edit_capturing_stderr("hash:" + h)
        finally:
            self._restore_no_editor_env(old_env)
            todo.subprocess.call, todo._find_editor = old_call, old_find
        self.assertEqual(code, 1)
        self.assertIn("editor launch disabled", err)
        self.assertIn("TODO_NO_EDITOR", err)
        self.assertEqual(calls, [], "no editor may be spawned when suppressed")

    def test_edit_launch_disabled_before_any_side_effect(self):
        # A refused edit must not bootstrap the Details Directory.
        h = self._add("Untouched issue")
        self.assertFalse(os.path.exists(os.path.join(todo.ISSUES_DIR, h)))
        old_env = self._with_no_editor_env('yes')
        try:
            code, err = self._edit_capturing_stderr("hash:" + h)
        finally:
            self._restore_no_editor_env(old_env)
        self.assertEqual(code, 1)
        self.assertIn("editor launch disabled", err)
        self.assertFalse(os.path.exists(os.path.join(todo.ISSUES_DIR, h)),
                         "suppressed launch must not create the Details Directory")

    def test_edit_enabled_when_env_unset(self):
        h = self._add("Editable issue")
        calls = []
        old_call, old_find = todo.subprocess.call, todo._find_editor
        todo.subprocess.call = lambda cmd: calls.append(cmd) or 0
        todo._find_editor = lambda: 'fake_editor'
        old_env = self._with_no_editor_env(None)
        try:
            todo.cmd_edit(_ns(identifier="hash:" + h, verbose=False))
        finally:
            self._restore_no_editor_env(old_env)
            todo.subprocess.call, todo._find_editor = old_call, old_find
        self.assertEqual(len(calls), 1, "editor must spawn when env is unset")
        self.assertEqual(calls[0][0], 'fake_editor')

    # ------------------------------------------------------------------
    # list --closed
    # ------------------------------------------------------------------

    def _list(self, **kw):
        # Run cmd_list with view flags defaulted; return its stdout text.
        kw.setdefault('closed', False)
        kw.setdefault('priority_filter', None)
        kw.setdefault('sort', None)
        kw.setdefault('reverse', False)
        out = _capture_stdout()
        old_out = sys.stdout
        sys.stdout = out
        try:
            todo.cmd_list(_ns(**kw))
        finally:
            sys.stdout = old_out
        return _as_text(out)

    def _rows(self, text):
        # Parsed (line number, line) view rows, in printed order.
        rows = []
        for raw in text.splitlines():
            m = re.match(r"\s*(\d+): (.*)$", raw)
            if m:
                rows.append((int(m.group(1)), m.group(2)))
        return rows

    def test_list_closed(self):
        h = self._add("Closable issue")
        todo.cmd_close(_ns(identifier="hash:"+h))
        text = self._list(closed=True)
        self.assertIn("Closed", text)
        self.assertIn(h, text)
        self.assertIn("Closable issue", text)

    # ------------------------------------------------------------------
    # list --sort / --reverse (ADR-0004: view flags, Index order kept)
    # ------------------------------------------------------------------

    def _seed_sort_rows(self):
        # Index order (append), deliberately unsorted on both keys.
        # Priorities present so the priority key has something to order.
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE,
                        "(C) 2026-11-05 charlie hash:cccccccc\n"
                        "(A) 2026-11-07 alpha hash:aaaaaaaa\n"
                        "(B) 2026-11-06 bravo hash:bbbbbbbb\n")

    def test_sort_priority_keeps_true_line_numbers(self):
        self._seed_sort_rows()
        rows = self._rows(self._list(sort='priority'))
        self.assertEqual([n for n, _l in rows], [2, 3, 1],
                         "A/B/C order; numbers are the TRUE Index lines")
        self.assertTrue(rows[0][1].startswith("(A)"), "A sorts first")
        self.assertTrue(rows[2][1].startswith("(C)"), "C sorts last")

    def test_sort_priority_reverse_keeps_buckets_last(self):
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE,
                        "(C) 2026-11-05 charlie hash:cccccccc\n"
                        "2026-11-07 unprioritised hash:dddddddd\n"
                        "(A) 2026-11-07 alpha hash:aaaaaaaa\n")
        rows = self._rows(self._list(sort='priority', reverse=True))
        self.assertEqual([n for n, _l in rows], [1, 3, 2],
                         "reversed sortable block (C,A), unprioritised still last")

    def test_sort_date_and_reverse(self):
        self._seed_sort_rows()
        rows = self._rows(self._list(sort='date'))
        self.assertEqual([n for n, _l in rows], [1, 3, 2], "oldest first")
        rows = self._rows(self._list(sort='date', reverse=True))
        self.assertEqual([n for n, _l in rows], [2, 3, 1], "newest first")

    def test_sort_date_buckets_undated_last_under_reverse(self):
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE,
                        "no date token here hash:dddddddd\n"
                        "2026-11-07 dated hash:aaaaaaaa\n"
                        "2026-11-05 older hash:bbbbbbbb\n")
        self.assertEqual([n for n, _l in self._rows(self._list(sort='date'))],
                         [3, 2, 1], "undated last going forward")
        self.assertEqual([n for n, _l in self._rows(self._list(sort='date', reverse=True))],
                         [2, 3, 1], "undated stays last when reversed")

    def test_sort_tie_break_is_index_order(self):
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE,
                        "(B) 2026-11-07 first b hash:bbbbbbbb\n"
                        "(B) 2026-11-07 second b hash:cccccccc\n"
                        "(A) 2026-11-07 an a hash:aaaaaaaa\n")
        self.assertEqual([n for n, _l in self._rows(self._list(sort='priority'))],
                         [3, 1, 2], "equal keys keep Index order")

    def test_reverse_without_sort_reverses_index_order(self):
        self._seed_sort_rows()
        self.assertEqual([n for n, _l in self._rows(self._list())], [1, 2, 3])
        self.assertEqual([n for n, _l in self._rows(self._list(reverse=True))], [3, 2, 1])

    def test_sort_applies_to_closed_list(self):
        todo.ensure_environment()
        self._write_raw(todo.DONE_FILE,
                        "x 2026-11-07 (C) 2026-11-05 older hash:cccccccc\n"
                        "x 2026-11-07 (A) 2026-11-07 newer hash:aaaaaaaa\n")
        rows = self._rows(self._list(closed=True, sort='priority'))
        self.assertEqual([n for n, _l in rows], [2, 1], "A before C in the Archive")
        rows = self._rows(self._list(closed=True, sort='date', reverse=True))
        self.assertEqual([n for n, _l in rows], [2, 1], "newest first")

    # ------------------------------------------------------------------
    # list --priority-filter grammar (ADR-0005)
    # ------------------------------------------------------------------

    def _seed_priority_rows(self):
        # Index order: A, C, B, unprioritised, Z.
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE,
                        "(A) 2026-11-01 a hash:aaaaaaaa\n"
                        "(C) 2026-11-02 c hash:cccccccc\n"
                        "(B) 2026-11-03 b hash:bbbbbbbb\n"
                        "2026-11-04 unprioritised hash:dddddddd\n"
                        "(Z) 2026-11-05 z hash:eeeeeeee\n")

    def _filtered_lines(self, spec, **kw):
        return [n for n, _l in self._rows(self._list(priority_filter=spec, **kw))]

    def _filter_error(self, spec, **kw):
        # Run the filter and return stderr text (asserting exit code 1).
        err = _capture_stderr()
        old_err = sys.stderr
        sys.stderr = err
        try:
            with self.assertRaises(SystemExit) as excinfo:
                self._list(priority_filter=spec, **kw)
        finally:
            sys.stderr = old_err
        self.assertEqual(excinfo.exception.code, 1,
                         "spec {!r} must fail loudly".format(spec))
        return _as_text(err)

    def test_priority_filter_exact(self):
        self._seed_priority_rows()
        self.assertEqual(self._filtered_lines("C"), [2])
        self.assertEqual(self._filtered_lines("A"), [1])

    def test_priority_filter_range(self):
        self._seed_priority_rows()
        self.assertEqual(self._filtered_lines("A-C"), [1, 2, 3],
                         "range keeps Index order")

    def test_priority_filter_and_better(self):
        self._seed_priority_rows()
        self.assertEqual(self._filtered_lines("C+"), [1, 2, 3], "C and better = A..C")
        self.assertEqual(self._filtered_lines("A+"), [1], "A+ is A alone")

    def test_priority_filter_and_worse(self):
        self._seed_priority_rows()
        self.assertEqual(self._filtered_lines("C-"), [2, 5], "C and worse = C..Z")
        self.assertEqual(self._filtered_lines("Z-"), [5], "Z- is Z alone")

    def test_priority_filter_case_insensitive_and_trimmed(self):
        self._seed_priority_rows()
        self.assertEqual(self._filtered_lines("c"), [2])
        self.assertEqual(self._filtered_lines(" a-c "), [1, 2, 3])
        self.assertEqual(self._filtered_lines("c+"), [1, 2, 3])

    def test_priority_filter_excludes_unprioritised(self):
        self._seed_priority_rows()
        # A..Z must not drag in the unprioritised line: a missing key is
        # not a priority.
        self.assertEqual(self._filtered_lines("A-Z"), [1, 2, 3, 5])

    def test_priority_filter_bound_forms_cover_the_whole_span(self):
        self._seed_priority_rows()
        # 'A-' is A and worse = A..Z, i.e. every prioritised issue. The
        # grammar has no exception for a bound at the range end (the plan
        # briefly listed 'A-' as rejected; settled 2026-11-07 in
        # ADR-0005: the grammar wins, no special-cased nonsense values).
        self.assertEqual(self._filtered_lines("A-"), [1, 2, 3, 5])
        self.assertEqual(self._filtered_lines("Z+"), [1, 2, 3, 5])
        self.assertEqual(self._filtered_lines("A+"), [1], "A and better is A alone")
        self.assertEqual(self._filtered_lines("Z-"), [5], "Z and worse is Z alone")

    def test_priority_filter_combines_with_sort(self):
        self._seed_priority_rows()
        self.assertEqual(self._filtered_lines("A-C", sort="priority", reverse=True),
                         [2, 3, 1], "filter then sorted, reversed: C, B, A")

    def test_priority_filter_rejects_bad_shapes(self):
        self._seed_priority_rows()
        for spec in ("ABC", "-C", "A-Z-", "C-A", "1", "(A)", ""):
            err = self._filter_error(spec)
            self.assertIn("invalid priority filter", err,
                          "spec {!r} needs a loud parse error".format(spec))
            self.assertIn("Accepted shapes" if spec == "C-A" else "accepted shapes",
                          err, "the accepted shapes must be in the message")
            self.assertIn("C, A-C, C+, C-", err,
                          "message must name every accepted shape: {!r}".format(spec))

    def test_priority_filter_swapped_range_is_not_silently_swapped(self):
        self._seed_priority_rows()
        err = self._filter_error("C-A")
        self.assertIn("below range end", err)

    def test_priority_filter_closed_accepts_exact_letter_only(self):
        todo.ensure_environment()
        self._write_raw(todo.DONE_FILE,
                        "x 2026-11-07 (C) 2026-11-05 c hash:cccccccc\n"
                        "x 2026-11-07 2026-11-06 plain hash:dddddddd\n")
        # Exact letter keeps today's substring behaviour.
        self.assertEqual(self._filtered_lines("C", closed=True), [1])
        self.assertEqual(self._filtered_lines("c", closed=True), [1])
        # Grammar specs fail loudly instead of printing an empty list.
        for spec in ("A-C", "C+", "C-", "ABC"):
            err = self._filter_error(spec, closed=True)
            self.assertIn("exact letter only", err)
            self.assertIn("hash:b8480e3f", err, "blocks-on reference must be named")


    def test_close_no_hash_line_mints_hash(self):
        # Manual no-hash line closed by line number: mint a hash at
        # close time; the archived line is addressable in done.txt.
        with open(todo.TODO_FILE, 'w') as f:
            f.write("manual no-hash line\n")
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            todo.cmd_close(_ns(identifier="1", verbose=False))
        finally:
            sys.stderr = old_stderr
        todo_lines = self._read(todo.TODO_FILE).splitlines()
        self.assertEqual(todo_lines, [])  # line removed
        done_lines = self._read(todo.DONE_FILE).splitlines()
        self.assertEqual(len(done_lines), 1)
        self.assertTrue(done_lines[0].startswith("x "))
        self.assertIn("manual no-hash line", done_lines[0])
        m = todo.HASH_IN_LINE_RE.search(done_lines[0])
        self.assertTrue(m, "minted hash missing from archived line")
        minted = m.group(1)
        # The minted hash is addressable in done.txt.
        resolved = todo.resolve_identifier(_ns(identifier="hash:" + minted, verbose=False),
                                           "hash:" + minted)
        self.assertEqual(resolved, minted)

    def test_close_twice_errors(self):
        h = self._add("Once only")
        todo.cmd_close(_ns(identifier="hash:"+h))
        stderr = _capture_stderr()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_close(_ns(identifier="hash:"+h))
        finally:
            sys.stderr = old_stderr
        self.assertEqual(excinfo.exception.code, 1)
        self.assertIn("might already be closed", _as_text(stderr))

    # ------------------------------------------------------------------
    # hash: mint hashes for Unhashed Lines (ADR-0003)
    # ------------------------------------------------------------------

    def _write_raw(self, path, text):
        # Byte-exact write: CRLF fixtures must survive the rewrite.
        f = io.open(path, 'w', encoding='utf-8', newline='')
        try:
            f.write(text)
        finally:
            f.close()

    def _read_raw(self, path):
        f = io.open(path, 'r', encoding='utf-8', newline='')
        try:
            return f.read()
        finally:
            f.close()

    def _mint(self, identifier=None):
        # Run cmd_hash quietly; return its stdout text.
        out = _capture_stdout()
        old_out = sys.stdout
        sys.stdout = out
        try:
            todo.cmd_hash(_ns(identifier=identifier, verbose=False))
        finally:
            sys.stdout = old_out
        return _as_text(out)

    def _mint_expecting_failure(self, identifier=None):
        stderr = _capture_stderr()
        old_err = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.cmd_hash(_ns(identifier=identifier, verbose=False))
        finally:
            sys.stderr = old_err
        self.assertEqual(excinfo.exception.code, 1)
        return _as_text(stderr)

    def test_hash_whole_file_preserves_bytes(self):
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE,
                        "first manual line\r\n"
                        "\r\n"
                        "2026-11-06 already hashed hash:deadbeef\r\n"
                        "last manual line")
        out = self._mint()
        raw = self._read_raw(todo.TODO_FILE)
        self.assertEqual(raw.count('\r\n'), 3)  # CRLF preserved
        self.assertTrue(raw.endswith("last manual line hash:" + raw.rsplit('hash:', 1)[1]))
        lines = raw.split('\r\n')
        self.assertEqual(lines[1], "")  # blank line untouched
        self.assertEqual(lines[2], "2026-11-06 already hashed hash:deadbeef")
        for idx in (0, 3):
            self.assertIsNotNone(todo._hash_of_line(lines[idx]),
                                 "line {} not minted: {!r}".format(idx + 1, lines[idx]))
            self.assertTrue(lines[idx].endswith(todo.HASH_IN_LINE_RE.search(lines[idx]).group(0)))
        self.assertIn("Minted 2 hash(es)", out)
        # The derived title is unchanged: hash appended at end of line.
        self.assertEqual(todo._title_from_line(lines[0]), "first manual line")

    def test_hash_idempotent_rerun_writes_nothing(self):
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE, "manual line one\r\nmanual line two\r\n")
        self._mint()
        after_first = self._read_raw(todo.TODO_FILE)
        self.assertEqual(after_first.count("hash:"), 2)
        out = self._mint()
        self.assertIn("nothing to mint", out)
        self.assertEqual(self._read_raw(todo.TODO_FILE), after_first)

    def test_hash_targeted_line_number_and_title(self):
        todo.ensure_environment()
        self._write_raw(todo.TODO_FILE,
                        "alpha manual line\r\n"
                        "beta manual line\r\n"
                        "2026-11-06 hashed line hash:deadbeef\r\n")
        self._mint(identifier="1")
        lines = self._read_raw(todo.TODO_FILE).split('\r\n')
        self.assertTrue(lines[0].startswith("alpha manual line hash:"))
        self.assertIsNone(todo._hash_of_line(lines[1]))
        # Title substring, restricted to Unhashed Lines.
        self._mint(identifier="BETA manual")
        lines = self._read_raw(todo.TODO_FILE).split('\r\n')
        self.assertTrue(lines[1].startswith("beta manual line hash:"))
        self.assertEqual(lines[2], "2026-11-06 hashed line hash:deadbeef")

    def test_hash_targeted_already_hashed_errors(self):
        self._add("Hashed already")
        h = self._extract_hash_from_todo()
        err = self._mint_expecting_failure(identifier="1")
        self.assertIn("already has hash:" + h, err)
        # Title of a hashed line is not a mint candidate either.
        err = self._mint_expecting_failure(identifier="Hashed already")
        self.assertIn("no Unhashed Line matching", err)

    def test_hash_collision_retries(self):
        todo.ensure_environment()
        # 'deadbeef' is already taken by a hashed line: the fake generator
        # returns it twice before a free one, exercising the retry loop.
        self._write_raw(todo.TODO_FILE,
                        "2026-11-06 hashed line hash:deadbeef\r\nmanual line\r\n")
        real_generate = todo.generate_hash
        seq = ['deadbeef', 'deadbeef', 'feedface']
        calls = []

        def fake_generate(title):
            value = seq[min(len(calls), len(seq) - 1)]
            calls.append(value)
            return value

        todo.generate_hash = fake_generate
        try:
            out = self._mint()
        finally:
            todo.generate_hash = real_generate
        self.assertEqual(len(calls), 3)  # two collisions, then a free hash
        self.assertIn("feedface", out)
        minted_line = self._read_raw(todo.TODO_FILE).splitlines()[1]
        self.assertEqual(todo._hash_of_line(minted_line), "feedface")

    def test_mint_hash_unique_fails_loudly_after_ten_tries(self):
        real_generate = todo.generate_hash
        calls = []

        def fake_generate(title):
            calls.append(title)
            return 'deadbeef'

        todo.generate_hash = fake_generate
        stderr = _capture_stderr()
        old_err = sys.stderr
        sys.stderr = stderr
        try:
            with self.assertRaises(SystemExit) as excinfo:
                todo.mint_hash_unique("title", ['deadbeef'])
        finally:
            todo.generate_hash = real_generate
            sys.stderr = old_err
        self.assertEqual(excinfo.exception.code, 1)
        self.assertEqual(len(calls), todo.MINT_ATTEMPTS)
        self.assertIn("could not mint a unique hash", _as_text(stderr))


# ----------------------------------------------------------------------
# help: `todo.py help` behaves as if --help was issued (hash:eb1deb21)
# ----------------------------------------------------------------------

class TestHelpCommand(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self._old_out, self._old_err = sys.stdout, sys.stderr
        self._old_argv = sys.argv
        sys.stdout, sys.stderr = _capture_stdout(), _capture_stderr()

    def tearDown(self):
        sys.argv = self._old_argv
        sys.stdout, sys.stderr = self._old_out, self._old_err
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)

    def _run(self, argv):
        sys.argv = ['todo.py'] + argv
        try:
            sys.stdout, sys.stderr = _capture_stdout(), _capture_stderr()
            try:
                todo.main()
            except SystemExit as e:
                code = e.code
            else:
                code = None
            return code, sys.stdout.getvalue(), sys.stderr.getvalue()
        finally:
            sys.stdout, sys.stderr = self._old_out, self._old_err

    def test_bare_help_equals_global_help(self):
        _, help_text, _ = self._run(['help'])
        _, dash_text, _ = self._run(['--help'])
        self.assertEqual(help_text, dash_text,
                         "todo.py help must print exactly what todo.py --help prints")

    def test_help_topic_prints_subcommand_help(self):
        _, via_help, _ = self._run(['help', 'add'])
        _, via_flag, _ = self._run(['add', '--help'])
        self.assertEqual(via_help, via_flag)
        self.assertIn('title', via_help)

    def test_help_unknown_topic_fails_loudly(self):
        code, _, err = self._run(['help', 'bogus'])
        self.assertEqual(code, 1, "expected exit 1 for unknown topic")
        self.assertIn('unknown help topic', err)

    def test_help_rejects_multiple_topics(self):
        code, _, err = self._run(['help', 'add', 'list'])
        self.assertEqual(code, 1, "expected exit 1 for multiple topics")
        self.assertIn('at most one topic', err)


# ----------------------------------------------------------------------
# md2todo.py: GFM task list import (ADR-0006, docs/plans/gfm-import.md)
# ----------------------------------------------------------------------

class TestGfmImport(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self._old_out, self._old_err = sys.stdout, sys.stderr
        self.out, self.err = _capture_stdout(), _capture_stderr()
        sys.stdout, sys.stderr = self.out, self.err

    def tearDown(self):
        sys.stdout, sys.stderr = self._old_out, self._old_err
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)

    # -- helpers -------------------------------------------------------

    def _source(self, text, name='in.md'):
        with io.open(name, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        return name

    def _import(self, text, argv_extra=None, expect_failure=False):
        # Run the CLI in-process; return (stdout text, stderr text, code).
        name = self._source(text)
        argv = [name] + list(argv_extra or [])
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = self.out, self.err
        try:
            code = 0
            try:
                md2todo.main(argv)
            except SystemExit as exc:
                code = exc.code
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        out, err = _as_text(self.out), _as_text(self.err)
        if expect_failure:
            self.assertEqual(code, 1, "expected exit 1; out={!r} err={!r}".format(out, err))
        else:
            self.assertEqual(code, 0, "unexpected failure: {!r}".format(err))
        return out, err

    def _read(self, path):
        with io.open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _todo_lines(self):
        if not os.path.exists(todo.TODO_FILE):
            return []
        return [l for l in self._read(todo.TODO_FILE).splitlines() if l]

    def _done_lines(self):
        if not os.path.exists(todo.DONE_FILE):
            return []
        return [l for l in self._read(todo.DONE_FILE).splitlines() if l]

    def _issue_md(self, line):
        h = todo._hash_of_line(line)
        self.assertIsNotNone(h, "no hash token in {!r}".format(line))
        path = os.path.join(todo.ISSUES_DIR, h, 'issue.md')
        self.assertTrue(os.path.exists(path), "missing issue.md for {}".format(h))
        return self._read(path)

    def _no_issue_md(self, line):
        h = todo._hash_of_line(line)
        path = os.path.join(todo.ISSUES_DIR, h, 'issue.md')
        self.assertFalse(os.path.exists(path), "unexpected issue.md for {}".format(h))

    # -- grammar -------------------------------------------------------

    def test_markers_and_checkbox_states(self):
        out, _err = self._import(
            "- [ ] dash open\n"
            "* [x] star checked\n"
            "+ [X] plus checked\n"
            "1. [ ] ordered dot\n"
            "7) [x] ordered paren\n")
        todo_lines = self._todo_lines()
        done_lines = self._done_lines()
        self.assertEqual(len(todo_lines), 2, "2 unchecked -> Index: {!r}".format(todo_lines))
        self.assertEqual(len(done_lines), 3, "3 checked -> Archive: {!r}".format(done_lines))
        self.assertTrue(todo_lines[0].endswith("dash open hash:" + todo._hash_of_line(todo_lines[0])))
        self.assertIn("star checked", done_lines[0])
        self.assertIn("plus checked", done_lines[1])
        self.assertIn("ordered dot", todo_lines[1])
        self.assertIn("ordered paren", done_lines[2])

    def test_empty_item_before_real_item_is_not_content(self):
        # A skipped empty item contributes no following content to the
        # next Issue: there is nothing between them but the skipped item.
        self._import("- [ ] \n- [ ] Real\n")
        self._no_issue_md(self._todo_lines()[0])

    def test_fenced_code_block_is_content_not_items(self):
        self._import("- [ ] real\n"
                     "```markdown\n"
                     "- [ ] fenced\n"
                     "```\n")
        self.assertEqual(len(self._todo_lines()), 1, "fenced checkbox must not be an Issue")
        body = self._issue_md(self._todo_lines()[0])
        self.assertIn("- [ ] fenced", body, "fenced content stays verbatim in issue.md")

    def test_inline_fence_is_self_contained(self):
        # hash:4ae2da8b-style inline fence: marker at line start AND close
        # marker on the same line. Python-string-literal style, not GFM;
        # seen in the wild (hash:6e6ac366 repro file). The line must be
        # fenced, and the fence must NOT swallow the rest of the file.
        self._import("- [ ] real\n"
                     "    ```[tool] call {...}...}```\n"
                     "- [ ] after\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 2, "inline fence must not swallow following items")
        body = self._issue_md(lines[0])
        self.assertIn("```[tool] call {...}...}```", body, "inline fence stays verbatim")

    def test_indented_bare_fence_marker_is_not_inline(self):
        # An indented fence marker ALONE on its line opens a fence; it is
        # not an inline fence. Regression: the first inline-fence fix
        # compared line.rstrip() (kept indentation) and misclassified
        # every indented '```' as an inline fence.
        self._import("- [ ] real\n"
                     "          ```\n"
                     "          log content\n"
                     "          ```\n"
                     "- [ ] after\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 2, "indented bare fence must not swallow following items")
        body = self._issue_md(lines[0])
        self.assertIn("log content", body, "fenced content stays verbatim in issue.md")

    def test_unclosed_fence_fails_hard(self):
        # hash:40f5fad4: an unclosed fence swallows everything after it to
        # EOF, silently losing items. The import must fail hard with the
        # line number of the fence opener.
        self._import("- [ ] real\n"
                     "```\n"
                     "fenced content\n"
                     "- [ ] swallowed\n"
                     "- [ ] also swallowed\n", expect_failure=True)
        self.assertEqual(self._todo_lines(), [], "import must not write anything")
        self.assertIn("unclosed fence", self.err.getvalue(), "error must name the problem")
        self.assertIn("line 2", self.err.getvalue(), "error must name the opener line")

    def test_unclosed_fence_no_items_after_fails_hard(self):
        # hash:40f5fad4: the fence is broken as a markdown document even
        # with no items after it, so the import must fail hard too.
        self._import("- [ ] real\n"
                     "```\n"
                     "fenced content\n", expect_failure=True)
        self.assertEqual(self._todo_lines(), [], "import must not write anything")
        self.assertIn("unclosed fence", self.err.getvalue(), "error must name the problem")
        self.assertIn("line 2", self.err.getvalue(), "error must name the opener line")

    def test_balanced_fence_imports_normally(self):
        # hash:40f5fad4: balanced fences are unchanged, imports fine.
        self._import("- [ ] real\n"
                     "```\n"
                     "fenced content\n"
                     "```\n"
                     "- [ ] after\n")
        self.assertEqual(len(self._todo_lines()), 2, "balanced fence imports fine")

    def test_indented_item_without_parent_is_top_level(self):
        self._import("    - [ ] deeply indented orphan\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 1)
        self.assertIn("deeply indented orphan", lines[0])

    # -- content attribution -------------------------------------------

    def test_preamble_goes_to_first_issue_nested_block_verbatim(self):
        self._import("# Title\n"
                     "\n"
                     "Intro prose.\n"
                     "\n"
                     "- [ ] Parent\n"
                     "  - [ ] child one\n"
                     "  between children\n"
                     "  - [x] child two\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 1, "children are not Issues: {!r}".format(lines))
        body = self._issue_md(lines[0])
        # Verbatim block model (ADR-0006 amendment 2026-11-08b): the
        # original lines lead the body, no dedent, no '# title' header
        # (the checkbox line IS the title line); preamble follows.
        self.assertEqual(body,
                         "- [ ] Parent\n"
                         "  - [ ] child one\n"
                         "  between children\n"
                         "  - [x] child two\n"
                         "\n"
                         "# Title\n"
                         "\n"
                         "Intro prose.\n",
                         "verbatim block first, preamble as preceding content")

    def test_content_between_issues_precedes_the_later_one(self):
        self._import("- [ ] A\n"
                     "  - [ ] a child\n"
                     "prose before B\n"
                     "\n"
                     "- [ ] B\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(self._issue_md(lines[0]), "- [ ] A\n  - [ ] a child\n")
        self.assertEqual(self._issue_md(lines[1]), "- [ ] B\n\nprose before B\n")


    def test_eof_content_goes_to_last_issue_under_notes(self):
        self._import("- [ ] Only\n"
                     "\n"
                     "trailing one\n"
                     "trailing two\n")
        body = self._issue_md(self._todo_lines()[0])
        self.assertEqual(body, "- [ ] Only\n\n## Notes\n\ntrailing one\ntrailing two\n")

    def test_indented_continuation_lines_attach_to_own_item(self):
        # Regression (real_test import, 2026-11-08): a "Done" note indented
        # under a checked item used to leak into the NEXT item's preceding
        # content, because _last_descendant_index only walked checkbox
        # children. Continuation lines deeper than the item's indent belong
        # to that item (ADR-0006 attribution amendment). "First" is checked
        # with no unchecked descendant, so it imports closed with its notes
        # in issue.md; "Second" is contentless.
        self._import("- [x] First\n"
                     "    -> Done (2026-11-08): fixed in foo.py.\n"
                     "    second note line\n"
                     "- [ ] Second\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 1, "Second is the only open Issue: {!r}".format(lines))
        self.assertIn("fixed in foo.py", self._issue_md(self._done_lines()[0]))
        self._no_issue_md(lines[0])

    def test_continuation_dedented_under_nested_block(self):
        self._import("- [ ] A\n"
                     "  - [ ] child\n"
                     "  -> note for A\n"
                     "- [ ] B\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(self._issue_md(lines[0]),
                         "- [ ] A\n  - [ ] child\n  -> note for A\n")
        self._no_issue_md(lines[1])

    def test_outdented_prose_between_items_still_precedes_next(self):
        # ADR-0006 baseline kept: unindented (outdented) prose between two
        # items is the NEXT item's preceding content, not the previous
        # item's notes. A is contentless here, so it gets no issue.md.
        self._import("- [ ] A\n"
                     "prose before B\n"
                     "- [ ] B\n")
        self._no_issue_md(self._todo_lines()[0])
        self.assertEqual(self._issue_md(self._todo_lines()[1]), "- [ ] B\n\nprose before B\n")

    def test_continuation_lines_are_not_items_and_not_state(self):
        # An indented "  - not a checkbox" line (no [ ]/[x]) must not be
        # parsed as an item; it is continuation content of the item above.
        self._import("- [ ] A\n"
                     "  - plain dash line\n"
                     "- [ ] B\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(self._issue_md(lines[0]), "- [ ] A\n  - plain dash line\n")
        self._no_issue_md(lines[1])

    def test_trailing_continuation_lines_go_to_notes_of_last_issue(self):
        self._import("- [ ] Only\n"
                     "  -> trailing note\n")
        body = self._issue_md(self._todo_lines()[0])
        self.assertIn("-> trailing note", body)

    def test_fenced_block_under_item_stays_with_item(self):
        # A code fence indented under an item must not be split off to the
        # next item even when its content is outdented.
        self._import("- [ ] A\n"
                     "  ```\n"
                     "outdented fenced line\n"
                     "  ```\n"
                     "- [ ] B\n")
        body = self._issue_md(self._todo_lines()[0])
        self.assertIn("outdented fenced line", body)
        self._no_issue_md(self._todo_lines()[1])

    def test_continuation_checked_item_with_notes_and_blank_runs(self):
        # Blank lines inside a continuation run are kept (verbatim slice
        # semantics); trailing blanks are trimmed by the region helpers.
        self._import("- [x] A\n"
                     "  note one\n"
                     "\n"
                     "  note two\n"
                     "- [ ] B\n")
        self.assertEqual(self._issue_md(self._done_lines()[0]),
                         "- [x] A\n  note one\n\n  note two\n")
        self._no_issue_md(self._todo_lines()[0])

    def test_blank_lines_trimmed_but_internal_ones_kept(self):
        self._import("\n\n"
                     "- [ ] Item\n"
                     "\n\n"
                     "  - [ ] first\n"
                     "\n"
                     "\n"
                     "  - [ ] second\n"
                     "\n\n")
        body = self._issue_md(self._todo_lines()[0])
        self.assertEqual(body,
                         "- [ ] Item\n\n\n"
                         "  - [ ] first\n"
                         "\n"
                         "\n"
                         "  - [ ] second\n",
                         "verbatim block keeps original indent and internal blank runs")

    def test_contentless_item_creates_no_issue_md(self):
        # A bare checkbox line with no subtree/content is not a verbatim
        # block worth storing (pure duplicate of the Index line).
        self._import("- [ ] bare\n")
        self._no_issue_md(self._todo_lines()[0])
        self.assertFalse(os.path.isdir(todo.ISSUES_DIR) and
                         os.listdir(todo.ISSUES_DIR), "no Details Directory expected")

    # -- state mapping -------------------------------------------------

    def test_checked_with_only_checked_descendants_imports_closed(self):
        self._import("- [x] Done\n"
                     "  - [x] child\n"
                     "     - [X] grandchild\n")
        self.assertEqual(self._todo_lines(), [], "fully checked subtree stays closed")
        done = self._done_lines()
        self.assertEqual(len(done), 1)
        self.assertTrue(done[0].startswith("x "), "Archive format: {!r}".format(done[0]))
        self.assertIn("Done", done[0])
        self.assertEqual(self._issue_md(done[0]),
                         "- [x] Done\n  - [x] child\n     - [X] grandchild\n")

    def test_checked_with_unchecked_descendant_imports_open_with_originally(self):
        self._import("- [x] Parent\n"
                     "  - [x] done child\n"
                     "  - [ ] open grandchild\n")
        todo_lines = self._todo_lines()
        self.assertEqual(len(todo_lines), 1, "must import open: {!r}".format(todo_lines))
        self.assertEqual(self._done_lines(), [])
        body = self._issue_md(todo_lines[0])
        self.assertEqual(body,
                         "- [x] Parent\n"
                         "  - [x] done child\n"
                         "  - [ ] open grandchild\n"
                         "\n"
                         "originally: - [x]\n",
                         "the original checked state is recorded after the verbatim block")

    def test_unchecked_imports_open_without_originally_record(self):
        self._import("- [ ] Todo\n  - [ ] child\n")
        body = self._issue_md(self._todo_lines()[0])
        self.assertEqual(body, "- [ ] Todo\n  - [ ] child\n")
        self.assertNotIn("originally:", body)

    # -- overlong titles -----------------------------------------------

    def test_overlong_title_truncated_in_index_and_hash_deterministic(self):
        title = " ".join("word{}".format(i) for i in range(60))
        self.assertGreater(len(title), md2todo.TITLE_LIMIT)
        self._import("- [ ] {}\n".format(title))
        line = self._todo_lines()[0]
        index_title = todo._title_from_line(line)
        self.assertTrue(index_title.endswith(md2todo.ELLIPSIS),
                        "overlong Index title must end with '...': {!r}".format(index_title))
        self.assertLessEqual(len(index_title), md2todo.TITLE_LIMIT + len(md2todo.ELLIPSIS))
        self.assertEqual(index_title, md2todo.truncate_title(title))
        # Truncated at a word boundary: no partial word before the dots.
        self.assertNotIn("wor" + md2todo.ELLIPSIS, index_title)
        self.assertNotIn(u"\u2026", index_title, "ASCII dots only, never a Unicode ellipsis")
        # Hash is minted from the truncated title (ADR-0006), title-only
        # and deterministic (md2todo amendment 2026-11-08c): the same
        # title produces the same hash, no timestamp involved.
        self.assertEqual(md2todo._generate_title_hash(index_title),
                         md2todo._generate_title_hash(index_title),
                         "hash must be deterministic for identical titles")
        self.assertEqual(todo._hash_of_line(line),
                         md2todo._generate_title_hash(index_title))
        # And a re-import of the same content FAILS LOUDLY (deterministic
        # hash already taken; md2todo amendment 2026-11-08c).
        first_hash = todo._hash_of_line(line)
        out, err = self._import("- [ ] {}\n".format(title), expect_failure=True)
        self.assertIn("already in the tracker as hash:" + first_hash, err)
        self.assertEqual(len(self._todo_lines()), 1, "failed import wrote nothing")

    def test_overlong_title_without_children_issue_md_is_plain_title(self):
        title = " ".join("word{}".format(i) for i in range(60))
        self._import("- [ ] {}\n".format(title))
        body = self._issue_md(self._todo_lines()[0])
        self.assertEqual(body, "- [ ] " + title + "\n\n" + title + "\n",
                         "verbatim block leads, then the full title as content")

    def test_overlong_title_with_children_keeps_full_header(self):
        title = " ".join("word{}".format(i) for i in range(60))
        self._import("- [ ] {}\n  - [ ] kid\n".format(title))
        body = self._issue_md(self._todo_lines()[0])
        self.assertEqual(body,
                         "- [ ] {}\n  - [ ] kid\n\n{}\n".format(title, title),
                         "verbatim block first; the full title follows as content, never truncated")

    def test_truncate_exactly_at_limit_is_untouched(self):
        title = "a" * md2todo.TITLE_LIMIT
        self.assertEqual(md2todo.truncate_title(title), title)
        self.assertEqual(md2todo.truncate_title("b" * (md2todo.TITLE_LIMIT + 1)),
                         "b" * md2todo.TITLE_LIMIT + md2todo.ELLIPSIS,
                         "a single long word is hard-cut")

    # -- skipped content -----------------------------------------------

    def test_empty_item_without_children_skipped_with_warning(self):
        out, err = self._import("- [ ] \n- [ ] Real\n- [ ] Another\n")
        self.assertIn("warning: skipped empty checklist item at line 1", err)
        lines = self._todo_lines()
        self.assertEqual(len(lines), 2, "only the real items are Issues: {!r}".format(lines))
        self.assertIn("Real", lines[0])
        self.assertIn("Another", lines[1])
        self.assertIn("2 issue(s)", out)

    def test_empty_item_with_children_promotes_children(self):
        _out, err = self._import("- [ ]\n"
                                 "   - [ ] child A\n"
                                 "      - [ ] grandchild of A\n"
                                 "   - [x] child B\n")
        self.assertIn("warning: skipped 1 empty checklist item", err)
        todo_lines = self._todo_lines()
        self.assertEqual(len(todo_lines), 1, "children promoted (open one): {!r}".format(todo_lines))
        self.assertIn("child A", todo_lines[0])
        self.assertIn("child B", self._done_lines()[0])
        self.assertEqual(self._issue_md(todo_lines[0]),
                         "   - [ ] child A\n      - [ ] grandchild of A\n",
                         "promoted children keep their original indentation")

    def test_only_empty_items_fails_loudly(self):
        out, err = self._import("- [ ]\n- [x]\n", expect_failure=True)
        self.assertIn("no checklist items found", err)
        self.assertEqual(self._todo_lines(), [])
        self.assertFalse(os.path.exists(todo.TODO_FILE), "no writes on failure")

    # -- metadata and tags ---------------------------------------------

    def test_titles_are_verbatim_no_token_extraction(self):
        self._import("- [ ] Fix thing +backend @bug ~2h #feature 2026-11-01\n")
        line = self._todo_lines()[0]
        self.assertEqual(todo._title_from_line(line),
                         "Fix thing +backend @bug ~2h #feature 2026-11-01",
                         "the whole line after the checkbox is the title")
        self.assertEqual(line.count("+backend"), 1)
        self.assertEqual(line.count("@bug"), 1)

    def test_global_tags_applied_to_every_issue(self):
        self._import("- [ ] one\n- [x] two\n", ['-p', 'b', '--project', 'backend',
                                                '--context', '@bug'])
        open_line = self._todo_lines()[0]
        closed_line = self._done_lines()[0]
        for line in (open_line, closed_line):
            self.assertIn("(B)", line)
            self.assertIn("+backend", line)
            self.assertIn("@bug", line)
        self.assertTrue(open_line.startswith("(B) "), "priority leads the Index line")
        self.assertEqual(closed_line.count("@bug"), 1, "no doubled @")

    # -- dry run -------------------------------------------------------

    def test_deterministic_hash_is_title_only_and_reimport_fails_loudly(self):
        # md2todo amendment 2026-11-08c: hashes derive from the (truncated)
        # title alone, no timestamp, so debugging an import is reproducible.
        out, _err = self._import("- [ ] alpha\n- [ ] beta\n")
        self.assertEqual(todo._hash_of_line(self._todo_lines()[0]),
                         md2todo._generate_title_hash("alpha"))
        # Re-import without cleanup: the same title hashes to the same
        # value, which is already taken -> loud failure, no silent
        # re-mint, no writes.
        _out, err = self._import("- [ ] alpha\n- [ ] gamma\n", expect_failure=True)
        first = todo._hash_of_line(self._todo_lines()[0])
        self.assertIn("already in the tracker as hash:" + first, err)
        self.assertEqual(len(self._todo_lines()), 2,
                         "alpha+beta from the first import; gamma must NOT be written")
        self.assertNotIn("gamma", self._todo_lines()[-1])

    def test_same_title_twice_in_one_file_gets_deterministic_suffix(self):
        self._import("- [ ] dup\n- [ ] dup\n")
        lines = self._todo_lines()
        self.assertEqual(len(lines), 2)
        hashes = [todo._hash_of_line(l) for l in lines]
        self.assertEqual(hashes[0], md2todo._generate_title_hash("dup"))
        self.assertNotEqual(hashes[0], hashes[1])
        self.assertEqual(hashes[1], md2todo._generate_title_hash("dup #1"),
                         "within-file duplicates retry deterministically")

    def test_dry_run_writes_nothing_and_prints_plan(self):
        out, _err = self._import("- [ ] open one\n"
                                 "- [x] closed one\n"
                                 "- [ ] with child\n"
                                 "  - [ ] kid\n",
                                 ['--dry-run'])
        self.assertIn("would create (open) line 1: open one", out)
        self.assertIn("would create (closed) -> done.txt: closed one", out)
        self.assertIn("would create issue.md:", out)
        self.assertIn("hashes are deterministic (title-only)", out)
        self.assertIn("would import 3 issue(s)", out)
        self.assertEqual(self._todo_lines(), [], "dry run must not write the Index")
        self.assertEqual(self._done_lines(), [], "dry run must not write the Archive")
        self.assertFalse(os.path.exists(todo.ISSUES_DIR), "dry run must not create directories")

    def test_dry_run_predicts_append_line_numbers(self):
        todo.ensure_environment()
        with io.open(todo.TODO_FILE, 'w', encoding='utf-8', newline='') as f:
            f.write("2026-11-06 existing hash:deadbeef\n")
        out, _err = self._import("- [ ] first\n- [ ] second\n", ['--dry-run'])
        self.assertIn("would create (open) line 2: first", out)
        self.assertIn("would create (open) line 3: second", out)

    # -- CLI -----------------------------------------------------------

    def test_flatten_is_reserved_and_fails_loudly(self):
        out, err = self._import("- [ ] a\n  - [ ] b\n", ['--flatten'], expect_failure=True)
        self.assertIn("--flatten is not implemented yet", err)
        self.assertEqual(self._todo_lines(), [])

    def test_missing_file_fails_loudly(self):
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = self.out, self.err
        try:
            with self.assertRaises(SystemExit) as excinfo:
                md2todo.main(['does-not-exist.md'])
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        self.assertEqual(excinfo.exception.code, 1)
        self.assertIn("file not found: does-not-exist.md", _as_text(self.err))

    def test_no_checklist_items_fails_loudly(self):
        _out, err = self._import("# Just a heading\n\nprose only\n", expect_failure=True)
        self.assertIn("no checklist items found", err)

    # -- hash uniqueness -----------------------------------------------

    def test_hashes_unique_across_import_and_existing_tokens(self):
        todo.ensure_environment()
        with io.open(todo.TODO_FILE, 'w', encoding='utf-8', newline='') as f:
            f.write("2026-11-06 taken hash:deadbeef\n")
        self._import("- [ ] one\n- [ ] two\n- [x] three\n")
        hashes = [todo._hash_of_line(l) for l in self._todo_lines() + self._done_lines()]
        self.assertEqual(len(set(hashes)), 4, "expected 4 distinct hashes: {!r}".format(hashes))
        self.assertEqual(hashes.count("deadbeef"), 1, "the existing token is untouched")
        self.assertEqual(len([h for h in hashes if h != "deadbeef"]), 3)

    def test_index_order_follows_source_order(self):
        self._import("- [x] first (closed)\n"
                     "- [ ] second\n"
                     "- [ ] third\n")
        titles = [todo._title_from_line(l) for l in self._todo_lines()]
        self.assertEqual(titles, ["second", "third"],
                         "open issues append in source order (ADR-0004)")


# ----------------------------------------------------------------------
# ADR-0017: configurable store location (--dir / --file, env vars)
# ----------------------------------------------------------------------

class TestStoreLocation(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self._old_out, self._old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _capture_stdout(), _capture_stderr()
        # Save the store constants; apply_store() mutates them globally.
        self._old = (todo.TODO_FILE, todo.DONE_FILE, todo.ISSUES_DIR)
        self._old_env = (os.environ.get('TODO_TRACKER_DIR'),
                         os.environ.get('TODO_FILE'))
        os.environ.pop('TODO_TRACKER_DIR', None)
        os.environ.pop('TODO_FILE', None)

    def tearDown(self):
        todo.TODO_FILE, todo.DONE_FILE, todo.ISSUES_DIR = self._old
        for name, value in (('TODO_TRACKER_DIR', self._old_env[0]),
                            ('TODO_FILE', self._old_env[1])):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        sys.stdout, sys.stderr = self._old_out, self._old_err
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)

    def _run(self, argv):
        sys.argv = ['todo.py'] + argv
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _capture_stdout(), _capture_stderr()
        try:
            try:
                todo.main()
            except SystemExit as e:
                code = e.code
            else:
                code = None
            out, err = sys.stdout.getvalue(), sys.stderr.getvalue()
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        # Normalize success (None) to 0 for assertions.
        return (0 if code is None else code), out, err

    def _read(self, path):
        with io.open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_apply_store_no_args_resets_to_relative_defaults(self):
        # Sanity: no flags/env -> constants stay relative, following cwd.
        todo.apply_store()
        self.assertEqual(todo.TODO_FILE, 'todo.txt')
        self.assertEqual(todo.DONE_FILE, 'done.txt')
        self.assertEqual(todo.ISSUES_DIR, '.issues')

    def test_dir_flag_relocates_bundle(self):
        store = os.path.join(self.test_dir, 'store')
        code, out, err = self._run(['add', '--dir', store, 'relocated issue'])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(store, 'todo.txt')))
        self.assertTrue(os.path.exists(os.path.join(store, 'done.txt')))
        self.assertTrue(os.path.isdir(os.path.join(store, '.issues')))
        # The absolute cwd store must NOT be polluted.
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'todo.txt')))
        # list works against the same store.
        code, out, err = self._run(['list', '--dir', store])
        self.assertEqual(code, 0, err)
        self.assertIn('relocated issue', out)

    def test_file_full_path_implies_parent_dir_for_bundle(self):
        store = os.path.join(self.test_dir, 'store')
        code, out, err = self._run(
            ['add', '--file', os.path.join(store, 'issues.txt'), 'full path issue'])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(store, 'issues.txt')))
        self.assertTrue(os.path.exists(os.path.join(store, 'done.txt')))
        self.assertTrue(os.path.isdir(os.path.join(store, '.issues')))
        code, out, err = self._run(
            ['list', '--file', os.path.join(store, 'issues.txt')])
        self.assertEqual(code, 0, err)
        self.assertIn('full path issue', out)

    def test_file_bare_name_plus_dir_combo(self):
        store = os.path.join(self.test_dir, 'store')
        code, out, err = self._run(
            ['add', '--file', 'issues.txt', '--dir', store, 'bare name issue'])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(store, 'issues.txt')))
        self.assertTrue(os.path.exists(os.path.join(store, 'done.txt')))
        self.assertTrue(os.path.isdir(os.path.join(store, '.issues')))
        self.assertFalse(os.path.exists(os.path.join(store, 'todo.txt')))

    def test_file_wins_over_dir_when_full_path(self):
        store = os.path.join(self.test_dir, 'store')
        other = os.path.join(self.test_dir, 'other')
        code, out, err = self._run(
            ['add', '--file', os.path.join(store, 'issues.txt'),
             '--dir', other, 'precedence issue'])
        self.assertEqual(code, 0, err)
        # --file is the most specific: the bundle lands in its parent dir.
        self.assertTrue(os.path.exists(os.path.join(store, 'issues.txt')))
        self.assertTrue(os.path.isdir(os.path.join(store, '.issues')))
        self.assertFalse(os.path.exists(os.path.join(other, 'todo.txt')))
        self.assertFalse(os.path.exists(os.path.join(other, '.issues')))

    def test_env_vars_override_defaults(self):
        store = os.path.join(self.test_dir, 'store')
        os.environ['TODO_TRACKER_DIR'] = store
        code, out, err = self._run(['add', 'env dir issue'])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(store, 'todo.txt')))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'todo.txt')))

        os.environ.pop('TODO_TRACKER_DIR')
        store3 = os.path.join(self.test_dir, 'store3')
        os.environ['TODO_FILE'] = os.path.join(store3, 'idx.txt')
        code, out, err = self._run(['add', 'env file issue'])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(store3, 'idx.txt')))
        self.assertTrue(os.path.isdir(os.path.join(store3, '.issues')))

    def test_flags_override_env_vars(self):
        store = os.path.join(self.test_dir, 'store')
        os.environ['TODO_TRACKER_DIR'] = os.path.join(self.test_dir, 'envstore')
        code, out, err = self._run(['add', '--dir', store, 'flag wins issue'])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(store, 'todo.txt')))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'envstore')))

    def test_missing_dir_auto_created(self):
        store = os.path.join(self.test_dir, 'nested', 'deep', 'store')
        code, out, err = self._run(['add', '--dir', store, 'deep issue'])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(store, 'todo.txt')),
                        "auto-create must mkdir -p the whole store path")

    def test_close_moves_line_to_done_in_relocated_bundle(self):
        store = os.path.join(self.test_dir, 'store')
        code, out, err = self._run(['add', '--dir', store, 'close me'])
        self.assertEqual(code, 0, err)
        code, out, err = self._run(['list', '--dir', store])
        self.assertEqual(code, 0, err)
        line = [l for l in out.splitlines() if 'close me' in l][0]
        n = int(line.split(':')[0].strip())
        code, out, err = self._run(['close', '--dir', store, str(n)])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(store, 'todo.txt')))
        self.assertIn('close me', self._read(os.path.join(store, 'done.txt')))
        self.assertNotIn('close me', self._read(os.path.join(store, 'todo.txt')))

    def test_messages_use_configured_file_name(self):
        store = os.path.join(self.test_dir, 'store')
        code, out, err = self._run(
            ['add', '--file', os.path.join(store, 'issues.txt'), 'named issue'])
        self.assertEqual(code, 0, err)
        # An in-range line WITHOUT a hash token makes the resolver name the
        # configured file; the message must not say 'todo.txt'.
        with io.open(os.path.join(store, 'issues.txt'), 'a') as f:
            f.write('\n')
        code, out, err = self._run(
            ['show', '--file', os.path.join(store, 'issues.txt'), '2'])
        self.assertEqual(code, 1, err)
        self.assertIn('issues.txt', err,
                      "error message must use the configured file name")
        self.assertNotIn('todo.txt', err,
                         "error message must not hardcode the default name")

    def test_show_and_comment_work_in_relocated_bundle(self):
        store = os.path.join(self.test_dir, 'store')
        code, out, err = self._run(['add', '--dir', store, 'describe me',
                                    '-d', 'body text'])
        self.assertEqual(code, 0, err)
        code, out, err = self._run(['show', '--dir', store, 'describe me'])
        self.assertEqual(code, 0, err)
        self.assertIn('body text', out)
        code, out, err = self._run(['comment', '--dir', store,
                                    'describe me', 'a note'])
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isdir(os.path.join(store, '.issues')))

    def test_md2todo_imports_into_relocated_bundle(self):
        store = os.path.join(self.test_dir, 'store')
        src = os.path.join(self.test_dir, 'in.md')
        with io.open(src, 'w', encoding='utf-8') as f:
            f.write('- [ ] imported issue\n')
        self._run_md2todo([src, '--dir', store])
        self.assertTrue(os.path.exists(os.path.join(store, 'todo.txt')))
        self.assertIn('imported issue', self._read(os.path.join(store, 'todo.txt')))
        self.assertTrue(os.path.isdir(os.path.join(store, '.issues')))

    def _run_md2todo(self, argv):
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _capture_stdout(), _capture_stderr()
        try:
            try:
                md2todo.main(argv)
            except SystemExit as e:
                code = e.code
            else:
                code = None
            err = sys.stderr.getvalue()
            out = sys.stdout.getvalue()
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        code = 0 if code is None else code
        self.assertEqual(code, 0, err)
        return out, err


if __name__ == '__main__':
    unittest.main()
