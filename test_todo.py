# -*- coding: utf-8 -*-
"""
Standard Library Unit Test Suite for Local Issue Tracker (todo.py)
Compatible with Python 2.7+ and Python 3.x using only unittest and tempfile.
"""
from __future__ import print_function, unicode_literals

import os
import sys
import shutil
import tempfile
import argparse
import unittest
import datetime

import todo

class TestLocalIssueTracker(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for each test to isolate todo.txt and .issues/
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        # Restore working directory and clean up temporary files
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)

    def _extract_hash_from_todo(self):
        with open(todo.TODO_FILE, 'r') as f:
            line = f.readline().strip()
        for part in line.split():
            if part.startswith("hash:"):
                return part.split(":")[1]
        return None

    def test_add_issue(self):
        args = argparse.Namespace(
            title="Fix critical login bug",
            description="Users receive a 500 error on OAuth callback.",
            priority="A",
            project="backend",
            context="auth"
        )
        todo.cmd_add(args)

        # Verify todo.txt index entry
        self.assertTrue(os.path.exists(todo.TODO_FILE))
        with open(todo.TODO_FILE, 'r') as f:
            content = f.read()

        self.assertIn("Fix critical login bug", content)
        self.assertIn("(A)", content)
        self.assertIn("hash:", content)
        self.assertIn("+backend", content)
        self.assertIn("@auth", content)

        # Verify directory structure and issue.md
        issue_hash = self._extract_hash_from_todo()
        self.assertIsNotNone(issue_hash)

        issue_dir = os.path.join(todo.ISSUES_DIR, issue_hash)
        self.assertTrue(os.path.isdir(issue_dir))
        self.assertTrue(os.path.isdir(os.path.join(issue_dir, 'comments')))
        self.assertTrue(os.path.isdir(os.path.join(issue_dir, 'attachments')))

        issue_md_path = os.path.join(issue_dir, 'issue.md')
        self.assertTrue(os.path.exists(issue_md_path))
        with open(issue_md_path, 'r') as f:
            desc = f.read()
        self.assertIn("Users receive a 500 error", desc)

    def test_comment_issue(self):
        # Add issue first
        add_args = argparse.Namespace(
            title="Refactor database connection pool",
            description=None,
            priority="B",
            project=None,
            context=None
        )
        todo.cmd_add(add_args)
        issue_hash = self._extract_hash_from_todo()

        # Add comment
        comment_args = argparse.Namespace(
            hash_prefix=issue_hash,
            text="Investigated connection limits; bumping pool size to 20."
        )
        todo.cmd_comment(comment_args)

        comments_dir = os.path.join(todo.ISSUES_DIR, issue_hash, 'comments')
        comment_files = os.listdir(comments_dir)
        self.assertEqual(len(comment_files), 1)
        self.assertTrue(comment_files[0].endswith(".md"))

        # Verify comment content
        with open(os.path.join(comments_dir, comment_files[0]), 'r') as f:
            body = f.read()
        self.assertIn("bumping pool size to 20", body)

    def test_close_issue(self):
        # Add issue
        add_args = argparse.Namespace(
            title="Update documentation for API endpoints",
            description="Needs OpenAPI 3.0 spec update.",
            priority=None,
            project=None,
            context=None
        )
        todo.cmd_add(add_args)
        issue_hash = self._extract_hash_from_todo()

        # Close issue
        close_args = argparse.Namespace(hash_prefix=issue_hash)
        todo.cmd_close(close_args)

        # Verify removed from todo.txt
        with open(todo.TODO_FILE, 'r') as f:
            todo_content = f.read()
        self.assertNotIn(issue_hash, todo_content)

        # Verify added to done.txt with completion prefix
        self.assertTrue(os.path.exists(todo.DONE_FILE))
        with open(todo.DONE_FILE, 'r') as f:
            done_content = f.read()
        self.assertIn(issue_hash, done_content)
        self.assertTrue(done_content.startswith("x "))

    def test_ambiguous_hash_prefix(self):
        # Add two issues
        todo.cmd_add(argparse.Namespace(title="First issue", description=None, priority=None, project=None, context=None))
        todo.cmd_add(argparse.Namespace(title="Second issue", description=None, priority=None, project=None, context=None))

        # Try showing with a non-existent prefix (should exit with status code 1)
        show_args = argparse.Namespace(hash_prefix="nonexistent")
        with self.assertRaises(SystemExit) as excinfo:
            todo.cmd_show(show_args)
        self.assertEqual(excinfo.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
