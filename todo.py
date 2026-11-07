#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Local Issue & Bug Tracker (Python 2 & 3 Compatible, Stdlib Only)
"""
from __future__ import print_function, unicode_literals

import os
import sys
import hashlib
import datetime
import argparse
import subprocess
import glob

TODO_FILE = 'todo.txt'
DONE_FILE = 'done.txt'
ISSUES_DIR = '.issues'

def ensure_environment():
    if not os.path.exists(ISSUES_DIR):
        os.makedirs(ISSUES_DIR)
    for filepath in [TODO_FILE, DONE_FILE]:
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                pass

def generate_hash(title):
    hasher = hashlib.sha256()
    timestamp = datetime.datetime.now().isoformat().encode('utf-8')
    hasher.update(title.encode('utf-8') + timestamp)
    return hasher.hexdigest()[:8]

def cmd_add(args):
    ensure_environment()
    issue_hash = generate_hash(args.title)
    today = datetime.date.today().isoformat()

    # Create issue directory structure
    issue_dir = os.path.join(ISSUES_DIR, issue_hash)
    comments_dir = os.path.join(issue_dir, 'comments')
    attachments_dir = os.path.join(issue_dir, 'attachments')

    for d in [issue_dir, comments_dir, attachments_dir]:
        if not os.path.exists(d):
            os.makedirs(d)

    # Write issue.md body
    issue_md_path = os.path.join(issue_dir, 'issue.md')
    with open(issue_md_path, 'w') as f:
        f.write(args.description or "# {}\n\nNo description provided.\n".format(args.title))

    # Format todo.txt line: [priority] [date] [title] hash:<id> [+project] [@context]
    line_parts = []
    if args.priority:
        line_parts.append("({})".format(args.priority.upper()))
    line_parts.append(today)
    line_parts.append(args.title)
    line_parts.append("hash:{}".format(issue_hash))

    if args.project:
        proj = args.project if args.project.startswith('+') else "+{}".format(args.project)
        line_parts.append(proj)
    if args.context:
        ctx = args.context if args.context.startswith('@') else "@{}".format(args.context)
        line_parts.append(ctx)

    new_line = " ".join(line_parts) + "\n"

    with open(TODO_FILE, 'r') as f:
        content = f.read()
    with open(TODO_FILE, 'w') as f:
        f.write(new_line + content)

    print("Created issue [{}] '{}'".format(issue_hash, args.title))

def cmd_list(args):
    ensure_environment()
    target_file = DONE_FILE if args.closed else TODO_FILE
    status_label = "Closed" if args.closed else "Open"

    print("\n--- {} Issues ({}) ---\n".format(status_label, target_file))
    with open(target_file, 'r') as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if args.priority and "({})".format(args.priority.upper()) not in line:
                continue
            print("{:2d}: {}".format(idx, line))
    print("")

def find_line_by_hash(filepath, target_hash):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if "hash:{}".format(target_hash) in line:
            return line.strip()
    return None

def cmd_show(args):
    ensure_environment()
    # Find matching hash folder
    matching_dirs = glob.glob(os.path.join(ISSUES_DIR, "{}*".format(args.hash_prefix)))
    if not matching_dirs:
        print("Error: No issue found matching hash prefix '{}'".format(args.hash_prefix), file=sys.stderr)
        sys.exit(1)
    if len(matching_dirs) > 1:
        print("Error: Ambiguous hash prefix '{}' matches multiple issues:".format(args.hash_prefix), file=sys.stderr)
        for d in matching_dirs:
            print("  - {}".format(os.path.basename(d)), file=sys.stderr)
        sys.exit(1)

    issue_dir = matching_dirs[0]
    full_hash = os.path.basename(issue_dir)

    # Locate index line in todo.txt or done.txt
    index_line = find_line_by_hash(TODO_FILE, full_hash) or find_line_by_hash(DONE_FILE, full_hash)

    print("==================================================")
    print("Issue Hash : {}".format(full_hash))
    if index_line:
        print("Index Line : {}".format(index_line))
    print("==================================================")

    issue_md_path = os.path.join(issue_dir, 'issue.md')
    if os.path.exists(issue_md_path):
        print("\n--- Description ---")
        with open(issue_md_path, 'r') as f:
            print(f.read().strip())

    comments_dir = os.path.join(issue_dir, 'comments')
    comment_files = sorted(glob.glob(os.path.join(comments_dir, '*.md')))
    if comment_files:
        print("\n--- Comments ---")
        for cf in comment_files:
            c_name = os.path.splitext(os.path.basename(cf))[0]
            print("\n[{}]".format(c_name))
            with open(cf, 'r') as f:
                print(f.read().strip())

    attachments_dir = os.path.join(issue_dir, 'attachments')
    attachments = os.listdir(attachments_dir)
    if attachments:
        print("\n--- Attachments ---")
        for att in attachments:
            print("  - {}".format(att))
    print("\n==================================================")

def cmd_comment(args):
    ensure_environment()
    matching_dirs = glob.glob(os.path.join(ISSUES_DIR, "{}*".format(args.hash_prefix)))
    if not matching_dirs:
        print("Error: No issue found matching hash prefix '{}'".format(args.hash_prefix), file=sys.stderr)
        sys.exit(1)
    issue_dir = matching_dirs[0]

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    comment_filename = "{}.md".format(timestamp)
    comment_path = os.path.join(issue_dir, 'comments', comment_filename)

    with open(comment_path, 'w') as f:
        f.write(args.text + "\n")

    print("Added comment to {} as {}".format(os.path.basename(issue_dir), comment_filename))

def cmd_close(args):
    ensure_environment()
    matching_dirs = glob.glob(os.path.join(ISSUES_DIR, "{}*".format(args.hash_prefix)))
    if not matching_dirs:
        print("Error: No issue found matching hash prefix '{}'".format(args.hash_prefix), file=sys.stderr)
        sys.exit(1)
    issue_dir = matching_dirs[0]
    full_hash = os.path.basename(issue_dir)

    # Read todo.txt, find line, remove, and append to done.txt with 'x YYYY-MM-DD'
    with open(TODO_FILE, 'r') as f:
        lines = f.readlines()

    new_todo_lines = []
    matched_line = None
    today = datetime.date.today().isoformat()

    for line in lines:
        if "hash:{}".format(full_hash) in line:
            clean_line = line.strip()
            # Format closed line: x YYYY-MM-DD <original_line>
            matched_line = "x {} {}\n".format(today, clean_line)
        else:
            new_todo_lines.append(line)

    if not matched_line:
        print("Error: Issue hash '{}' not found in active {} (might already be closed).".format(full_hash, TODO_FILE), file=sys.stderr)
        sys.exit(1)

    with open(TODO_FILE, 'w') as f:
        f.writelines(new_todo_lines)

    with open(DONE_FILE, 'a') as f:
        f.write(matched_line)

    print("Closed and archived issue [{}]".format(full_hash))

def cmd_edit(args):
    ensure_environment()
    matching_dirs = glob.glob(os.path.join(ISSUES_DIR, "{}*".format(args.hash_prefix)))
    if not matching_dirs:
        print("Error: No issue found matching hash prefix '{}'".format(args.hash_prefix), file=sys.stderr)
        sys.exit(1)
    issue_dir = matching_dirs[0]
    issue_md_path = os.path.join(issue_dir, 'issue.md')

    editor = os.environ.get('EDITOR', 'nano')
    try:
        subprocess.call([editor, issue_md_path])
    except OSError as e:
        print("Error launching editor '{}': {}".format(editor, e), file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Local Repository Issue & Bug Tracker (todo.txt + flat files)")
    subparsers = parser.add_subparsers(dest='command', help='Sub-command to run')

    # add
    parser_add = subparsers.add_parser('add', help='Create a new issue')
    parser_add.add_argument('title', help='Issue summary / title')
    parser_add.add_argument('-d', '--description', help='Extended description body', default=None)
    parser_add.add_argument('-p', '--priority', help='Priority letter (A-Z)', default=None)
    parser_add.add_argument('--project', help='Project tag (e.g. +backend)', default=None)
    parser_add.add_argument('--context', help='Context tag (e.g. @bug)', default=None)

    # list / ls
    parser_list = subparsers.add_parser('list', help='List issues')
    parser_list.add_argument('--closed', action='store_true', help='List closed issues from done.txt')
    parser_list.add_argument('-p', '--priority', help='Filter by priority', default=None)

    # show
    parser_show = subparsers.add_parser('show', help='Inspect issue details, description, and comments')
    parser_show.add_argument('hash_prefix', help='Full or partial issue hash')

    # comment
    parser_comment = subparsers.add_parser('comment', help='Add a timestamped comment to an issue')
    parser_comment.add_argument('hash_prefix', help='Full or partial issue hash')
    parser_comment.add_argument('text', help='Comment text')

    # close
    parser_close = subparsers.add_parser('close', help='Close an issue and archive it to done.txt')
    parser_close.add_argument('hash_prefix', help='Full or partial issue hash')

    # edit
    parser_edit = subparsers.add_parser('edit', help='Open issue description in $EDITOR')
    parser_edit.add_argument('hash_prefix', help='Full or partial issue hash')

    args = parser.parse_args()

    if args.command == 'add':
        cmd_add(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'show':
        cmd_show(args)
    elif args.command == 'comment':
        cmd_comment(args)
    elif args.command == 'close':
        cmd_close(args)
    elif args.command == 'edit':
        cmd_edit(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
