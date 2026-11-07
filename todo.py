#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Local Issue & Bug Tracker (Python 2 & 3 Compatible, Stdlib Only)
"""
from __future__ import print_function, unicode_literals

import os
import re
import sys
import hashlib
import datetime
import argparse
import subprocess
import glob

TODO_FILE = 'todo.txt'
DONE_FILE = 'done.txt'
ISSUES_DIR = '.issues'

HEX_RE = re.compile(r'^[0-9a-fA-F]+$')

# UTC source compatible with py2 (no datetime.timezone) and py3.12+
# (datetime.utcnow() deprecated).
try:
    _UTC = datetime.timezone.utc
except AttributeError:
    _UTC = None

def _utcnow():
    if _UTC is not None:
        return datetime.datetime.now(_UTC)
    return datetime.datetime.utcnow()
DIGITS_RE = re.compile(r'^[0-9]+$')
HASH_IN_LINE_RE = re.compile(r'hash:([0-9a-fA-F]+)')
PRIORITY_RE = re.compile(r'^\([A-Z]\)$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

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

def _trace(args, msg):
    # Trace-level output for major steps; only under --verbose.
    # Fails fast (AttributeError) if args lacks the verbose attribute.
    if args.verbose:
        print("trace: {}".format(msg))

def _fail(msg):
    print("Error: {}".format(msg), file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Identifier resolution (shared by show / comment / close / edit)
#
# Dispatch order:
#   1. 'hash:<hex>'  explicit form, prefix allowed (glob in .issues/)
#   2. all-digits    -> 1-based line number in todo.txt (active list),
#                       matching exactly what `list` prints (blank lines
#                       included in numbering). No fall-through.
#   3. hex-like      (^[0-9a-fA-F]+$) -> hash prefix first, then title.
#                       When hash wins over a title match, a note is
#                       printed ALWAYS (not only under --verbose).
#   4. otherwise     -> case-insensitive substring match against active
#                       todo.txt titles.
#
# Returns one full hash. Any failure or ambiguity exits(1) with stderr
# details listing both hash and title matches. Each command applies its
# own post-resolution validation (e.g. close requires presence in
# todo.txt). Residual edge (accepted): digit-only titles are unreachable
# by bare token; use hash:<hex> for those.
# ---------------------------------------------------------------------------

def _glob_hash_prefix(prefix):
    # Hash tokens live in todo.txt/done.txt lines; the .issues/<hash>/
    # directory is lazily created storage and may not exist. Match
    # against hash: tokens instead of globbing directories.
    matches = []
    for filepath in [TODO_FILE, DONE_FILE]:
        if not os.path.exists(filepath):
            continue
        with open(filepath, 'r') as f:
            for line in f:
                h = _hash_of_line(line.strip())
                if h and h.startswith(prefix):
                    matches.append((h, line.strip()))
    return matches

def _title_from_line(line):
    parts = line.split()
    cut = None
    for i, part in enumerate(parts):
        if part.startswith('hash:'):
            cut = i
            break
    if cut is not None:
        parts = parts[:cut]
    while parts and (PRIORITY_RE.match(parts[0]) or DATE_RE.match(parts[0])):
        parts.pop(0)
    return ' '.join(parts)

def _title_matches(token):
    # Case-insensitive substring match against active todo.txt titles only.
    matches = []
    with open(TODO_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            title = _title_from_line(line)
            if token.lower() in title.lower():
                matches.append({'title': title, 'line': line})
    return matches

def _hash_of_line(line):
    m = HASH_IN_LINE_RE.search(line)
    if not m:
        return None
    return m.group(1)

def _fail_ambiguous(token, hash_matches, title_matches):
    print("Error: Ambiguous identifier '{}' matches multiple issues:".format(token), file=sys.stderr)
    if hash_matches:
        print("  hash matches:", file=sys.stderr)
        for h in hash_matches:
            print("    - {}".format(h), file=sys.stderr)
    if title_matches:
        print("  title matches:", file=sys.stderr)
        for m in title_matches:
            h = _hash_of_line(m['line'])
            suffix = "[hash:{}]".format(h) if h else "[no hash token]"
            print("    - '{}' {}".format(m['title'], suffix), file=sys.stderr)
    sys.exit(1)

def _pick_title_match(args, token, matches):
    if not matches:
        _fail("No issue found matching title substring '{}' in {}".format(token, TODO_FILE))
    if len(matches) > 1:
        _fail_ambiguous(token, [], matches)
    line = matches[0]['line']
    h = _hash_of_line(line)
    if not h:
        _fail("Line for title match '{}' has no hash: token: {}".format(token, line))
    _trace(args, "resolve: '{}' -> {} via title".format(token, h))
    return h

def _resolve_line_number(args, token):
    n = int(token)
    with open(TODO_FILE, 'r') as f:
        lines = f.readlines()
    if n < 1 or n > len(lines):
        _fail("no line {} in {} (1..{}); for hashes use hash:<hex>".format(n, TODO_FILE, len(lines)))
    line = lines[n - 1].strip()
    h = _hash_of_line(line)
    if not h:
        _fail("line {} in {} has no hash: token: {}".format(n, TODO_FILE, line))
    _trace(args, "resolve: '{}' -> {} via line number".format(token, h))
    return h

def _resolve_hash_form(args, prefix, explicit):
    matches = _glob_hash_prefix(prefix)
    # Distinct hashes matching this prefix.
    hashes = []
    for h, _line in matches:
        if h not in hashes:
            hashes.append(h)
    if len(hashes) > 1:
        _fail_ambiguous(prefix, hashes, _title_matches(prefix))
    if len(hashes) == 1:
        full_hash = hashes[0]
        if not explicit:
            titles = _title_matches(prefix)
            if titles:
                names = ", ".join("'{}'".format(m['title']) for m in titles)
                print("Note: '{}' resolved via hash {} (also matches title(s): {})".format(prefix, full_hash, names))
        _trace(args, "resolve: '{}' -> {} via hash prefix".format(prefix, full_hash))
        return full_hash
    # Zero hash matches: fall through to title matching.
    titles = _title_matches(prefix)
    if titles:
        return _pick_title_match(args, prefix, titles)
    _fail("No issue found matching hash prefix or title '{}'".format(prefix))

def resolve_identifier(args, token):
    _trace(args, "resolve: token '{}'".format(token))
    if token.startswith('hash:'):
        return _resolve_hash_form(args, token[len('hash:'):], explicit=True)
    if DIGITS_RE.match(token):
        return _resolve_line_number(args, token)
    if HEX_RE.match(token):
        return _resolve_hash_form(args, token, explicit=False)
    return _pick_title_match(args, token, _title_matches(token))

# ---------------------------------------------------------------------------

def _ensure_issue_dir(issue_hash):
    # Lazily create the hash directory; nothing is created for a
    # description-less issue until a comment, edit, or description exists.
    issue_dir = os.path.join(ISSUES_DIR, issue_hash)
    if not os.path.exists(issue_dir):
        os.makedirs(issue_dir)
    return issue_dir

def cmd_add(args):
    ensure_environment()
    issue_hash = generate_hash(args.title)
    today = datetime.date.today().isoformat()

    # Only a description warrants a Details Directory and issue.md.
    # Title-only issues index in todo.txt alone; comment/edit bootstrap
    # the directory lazily.
    if args.description:
        issue_dir = _ensure_issue_dir(issue_hash)
        with open(os.path.join(issue_dir, 'issue.md'), 'w') as f:
            f.write(args.description)
    else:
        _trace(args, "add: no description; no issue dir created for {}".format(issue_hash))

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
    full_hash = resolve_identifier(args, args.identifier)
    issue_dir = os.path.join(ISSUES_DIR, full_hash)

    # Locate index line in todo.txt or done.txt
    index_line = find_line_by_hash(TODO_FILE, full_hash) or find_line_by_hash(DONE_FILE, full_hash)

    print("==================================================")
    print("Issue Hash : {}".format(full_hash))
    if index_line:
        print("Index Line : {}".format(index_line))
    print("==================================================")

    if os.path.exists(issue_dir):
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
        attachments = os.listdir(attachments_dir) if os.path.isdir(attachments_dir) else []
        if attachments:
            print("\n--- Attachments ---")
            for att in attachments:
                print("  - {}".format(att))
    print("\n==================================================")

def cmd_comment(args):
    ensure_environment()
    full_hash = resolve_identifier(args, args.identifier)
    issue_dir = _ensure_issue_dir(full_hash)
    comments_dir = os.path.join(issue_dir, 'comments')
    if not os.path.exists(comments_dir):
        os.makedirs(comments_dir)

    # UTC timestamp, seconds precision, one format, no collision handling.
    timestamp = _utcnow().strftime('%Y%m%d_%H%M%S')
    comment_filename = "{}.md".format(timestamp)
    comment_path = os.path.join(comments_dir, comment_filename)

    with open(comment_path, 'w') as f:
        f.write(args.text + "\n")

    print("Added comment to {} as {}".format(full_hash, comment_filename))

def cmd_close(args):
    ensure_environment()
    full_hash = resolve_identifier(args, args.identifier)

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

def _which(program):
    # shutil.which is Python 3 only; minimal stdlib equivalent for py2/3.
    path_env = os.environ.get('PATH', '')
    extensions = ['']
    if os.name == 'nt':
        pathext = os.environ.get('PATHEXT', '.COM;.EXE;.BAT;.CMD')
        extensions = [''] + [e for e in pathext.split(';') if e]
    for dirpath in path_env.split(os.pathsep):
        if not dirpath:
            continue
        for ext in extensions:
            candidate = os.path.join(dirpath, program + ext)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None

def _find_editor():
    # Chain: $EDITOR -> $VISUAL -> which-scan (vim, nano, vi) -> notepad
    # on Windows -> None (caller fails loudly).
    for var in ('EDITOR', 'VISUAL'):
        value = os.environ.get(var)
        if value:
            return value
    for candidate in ('vim', 'nano', 'vi'):
        path = _which(candidate)
        if path:
            return path
    if os.name == 'nt':
        path = _which('notepad')
        if path:
            return path
    return None

def cmd_edit(args):
    ensure_environment()
    full_hash = resolve_identifier(args, args.identifier)
    # Bootstrap: a description-less issue has no Details Directory yet;
    # editing is exactly when the description gets written.
    issue_dir = _ensure_issue_dir(full_hash)
    issue_md_path = os.path.join(issue_dir, 'issue.md')
    if not os.path.exists(issue_md_path):
        with open(issue_md_path, 'w') as f:
            line = find_line_by_hash(TODO_FILE, full_hash) or find_line_by_hash(DONE_FILE, full_hash)
            title = _title_from_line(line) if line else full_hash
            f.write("# {}\n".format(title))

    editor = _find_editor()
    if not editor:
        _fail("no editor found; set $EDITOR or $VISUAL (e.g. export EDITOR=vim)")
    _trace(args, "edit: launching editor '{}' on {}".format(editor, issue_md_path))
    # TODO: EDITOR values containing arguments (e.g. "code -w") are not
    # supported; the whole value is used as the executable name.
    try:
        subprocess.call([editor, issue_md_path])
    except OSError as e:
        print("Error launching editor '{}': {}".format(editor, e), file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Local Repository Issue & Bug Tracker (todo.txt + flat files)")
    subparsers = parser.add_subparsers(dest='command', help='Sub-command to run')

    # Shared flags (verbose OFF by default)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--verbose', action='store_true', default=False,
                        help='Trace-level output for major steps')

    # add
    parser_add = subparsers.add_parser('add', parents=[common], help='Create a new issue')
    parser_add.add_argument('title', help='Issue summary / title')
    parser_add.add_argument('-d', '--description', help='Extended description body', default=None)
    parser_add.add_argument('-p', '--priority', help='Priority letter (A-Z)', default=None)
    parser_add.add_argument('--project', help='Project tag (e.g. +backend)', default=None)
    parser_add.add_argument('--context', help='Context tag (e.g. @bug)', default=None)

    # list / ls
    parser_list = subparsers.add_parser('list', parents=[common], help='List issues')
    parser_list.add_argument('--closed', action='store_true', help='List closed issues from done.txt')
    parser_list.add_argument('-p', '--priority', help='Filter by priority', default=None)

    # show
    parser_show = subparsers.add_parser('show', parents=[common], help='Inspect issue details, description, and comments')
    parser_show.add_argument('identifier', help='Issue identifier: hash:<hex>, line number, hash prefix, or title substring')

    # comment
    parser_comment = subparsers.add_parser('comment', parents=[common], help='Add a timestamped comment to an issue')
    parser_comment.add_argument('identifier', help='Issue identifier: hash:<hex>, line number, hash prefix, or title substring')
    parser_comment.add_argument('text', help='Comment text')

    # close
    parser_close = subparsers.add_parser('close', parents=[common], help='Close an issue and archive it to done.txt')
    parser_close.add_argument('identifier', help='Issue identifier: hash:<hex>, line number, hash prefix, or title substring')

    # edit
    parser_edit = subparsers.add_parser('edit', parents=[common], help='Open issue description in $EDITOR')
    parser_edit.add_argument('identifier', help='Issue identifier: hash:<hex>, line number, hash prefix, or title substring')

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
