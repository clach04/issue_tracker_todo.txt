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
        # add prepends: the new issue is line 1, the fixture line 2.
        self.assertEqual(todo._hash_of_line(lines[0]), "feedface",
                         "add must store the first unique candidate")
        self.assertEqual(todo._hash_of_line(lines[1]), "deadbeef",
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
        # cmd_add prepends; Beta is line 1, Alpha is line 2.
        self.assertEqual(todo.resolve_identifier(_ns(identifier="1", verbose=False), "1"), h2)
        self.assertEqual(todo.resolve_identifier(_ns(identifier="2", verbose=False), "2"), h1)

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

    def test_list_closed(self):
        h = self._add("Closable issue")
        todo.cmd_close(_ns(identifier="hash:"+h))
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


if __name__ == '__main__':
    unittest.main()
