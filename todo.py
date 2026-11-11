#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Local Issue & Bug Tracker (Python 2 & 3 Compatible, Stdlib Only)
"""
from __future__ import print_function, unicode_literals

import io
import os
import re
import sys
import hashlib
import datetime
import argparse
import subprocess
import glob
import io

IS_PY3 = sys.version_info >= (3,)

def read_stdin_bytes():
    # Byte-faithful stdin read (comment dash-marker plan; same idiom as
    # ptcipher.py): py3 exposes raw bytes via sys.stdin.buffer; py2's
    # sys.stdin is a file object whose read() already returns raw bytes.
    # Asserted, not assumed - fails loudly if neither shape appears.
    if IS_PY3:
        assert hasattr(sys.stdin, 'buffer'), (
            "expected py3 stdin with .buffer, got {}".format(type(sys.stdin)))
        return sys.stdin.buffer.read()
    assert hasattr(sys.stdin, 'read'), (
        "expected py2 file-like stdin, got {}".format(type(sys.stdin)))
    return sys.stdin.read()

DASH_MARKER = '-'

# Store location (ADR-0017): the store is a bundle - todo.txt + done.txt
# + .issues/ all live in ONE directory. Env vars are read ONCE at import
# time into the defaults; CLI flags override them via apply_store(). With
# no env vars set the constants stay relative (cwd), so existing tests
# and the web UI's cwd-based path joins keep working unchanged.
DEFAULT_TODO_FILE = 'todo.txt'
DEFAULT_DONE_FILE = 'done.txt'
DEFAULT_ISSUES_DIR = '.issues'

TODO_FILE = DEFAULT_TODO_FILE
DONE_FILE = DEFAULT_DONE_FILE
ISSUES_DIR = DEFAULT_ISSUES_DIR


def apply_store(dir_value=None, file_value=None):
    """Resolve the store bundle (ADR-0017) and mutate the module constants.

    Precedence: CLI flags (dir_value / file_value) > env vars
    (TODO_TRACKER_DIR / TODO_FILE) > defaults. A --file FULL PATH implies
    its parent directory for the whole bundle (done.txt and .issues/ move
    there); a bare file name only changes the todo index name. --dir
    relocates the bundle directory with file names fixed. Relative paths
    resolve against cwd at call time. No directory is created here;
    ensure_environment() auto-creates them (mkdir -p semantics).
    """
    dir_val = dir_value if dir_value is not None else os.environ.get('TODO_TRACKER_DIR')
    file_val = file_value if file_value is not None else os.environ.get('TODO_FILE')

    todo_name = DEFAULT_TODO_FILE
    if file_val is not None:
        parent = os.path.dirname(file_val)
        if parent:
            # Full path implies its own parent dir for the whole bundle;
            # --file wins over --dir in that case (ADR-0017).
            dir_val = parent
        todo_name = os.path.basename(file_val)
    if dir_val is not None:
        # Explicit dir (or --file parent): absolutize once so the store
        # location is stable regardless of later cwd changes.
        dir_val = os.path.abspath(dir_val)
    else:
        # No explicit dir: keep the constants RELATIVE (cwd-relative) so
        # they follow the process cwd, as they always have.
        dir_val = None

    global TODO_FILE, DONE_FILE, ISSUES_DIR
    if dir_val is None:
        TODO_FILE = todo_name
        DONE_FILE = DEFAULT_DONE_FILE
        ISSUES_DIR = DEFAULT_ISSUES_DIR
    else:
        TODO_FILE = os.path.join(dir_val, todo_name)
        DONE_FILE = os.path.join(dir_val, DEFAULT_DONE_FILE)
        ISSUES_DIR = os.path.join(dir_val, DEFAULT_ISSUES_DIR)


if os.environ.get('TODO_TRACKER_DIR') or os.environ.get('TODO_FILE'):
    apply_store()

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

# ADR-0005 priority filter grammar: 'C', 'A-C', 'C+', 'C-'. Parsed, never
# substring-matched: an unparsable spec must fail loudly, because an empty
# result reads as "no matching issues".
PRIORITY_LETTER_RE = re.compile(r'^[A-Z]$')
PRIORITY_RANGE_RE = re.compile(r'^([A-Z])-([A-Z])$')
PRIORITY_BOUND_RE = re.compile(r'^([A-Z])([+-])$')
PRIORITY_FILTER_SHAPES = "C, A-C, C+, C- (A is highest)"

def ensure_environment():
    # ADR-0017: the store dir may not exist yet (e.g. --dir ~/notes/empty);
    # auto-create it (mkdir -p semantics) - a missing dir is a valid empty
    # tracker. os.makedirs creates parents too.
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

MINT_ATTEMPTS = 10

def mint_hash_unique(title, taken):
    """Mint a hash not in 'taken' (iterable of short hashes).

    ADR-0003: every minting path ('add', 'hash', close-time) retries
    until the hash is unique across todo.txt and done.txt.
    """
    for _attempt in range(MINT_ATTEMPTS):
        candidate = generate_hash(title)
        if candidate not in taken:
            return candidate
    _fail("could not mint a unique hash for {!r} after {} attempts".format(title, MINT_ATTEMPTS))

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

def _in_range_line(token):
    """Return the raw stripped line for an in-range all-digit token, else None.

    Out-of-range means 'not a line number' (todo.txt stays small); the
    caller falls through to hash then title lookup (ADR-0002).
    """
    if not DIGITS_RE.match(token):
        return None
    with open(TODO_FILE, 'r') as f:
        lines = f.readlines()
    n = int(token)
    if n < 1 or n > len(lines):
        return None
    return lines[n - 1].strip()

def _resolve_line_number(args, token):
    line = _in_range_line(token)
    if line is None:
        _trace(args, "resolve: '{}' out of range; not a line number".format(token))
        return None
    h = _hash_of_line(line)
    if not h:
        _fail("line {} in {} has no hash: token: {}".format(token, TODO_FILE, line))
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
        # In-range all-digit tokens are Index line numbers. Out-of-range
        # (todo.txt is small) means 'not a line number': fall through to
        # hash prefix, then title (ADR-0002).
        resolved = _resolve_line_number(args, token)
        if resolved is not None:
            return resolved
        if HEX_RE.match(token):
            return _resolve_hash_form(args, token, explicit=False)
        return _pick_title_match(args, token, _title_matches(token))
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
    # ADR-0003: add mints with the same uniqueness retry as 'hash' and
    # close-time minting. 'taken' must be read before the new line exists.
    issue_hash = mint_hash_unique(args.title, _all_hash_tokens())
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
    new_line = format_index_line(args.title, issue_hash, priority=args.priority,
                                 project=args.project, context=args.context,
                                 date=today) + "\n"

    # ADR-0004: `add` APPENDS, so it never renumbers an existing line.
    # Prepending renumbered every Issue on every add and silently
    # invalidated any remembered line number. (A line number is only
    # stable while the issue stays open: close removes its line and
    # shifts later numbers; hand edits can renumber too.)
    line_number = append_index_line(new_line)
    print("Created issue [{}] at line {}: '{}'".format(issue_hash, line_number, args.title))

def format_index_line(title, issue_hash, priority=None, project=None,
                      context=None, date=None):
    """Format an Index line: [priority] [date] [title] hash:<h> [+p] [@c].

    Shared by `add` and the GFM import (md2todo.py), ADR-0006: the import
    must reuse the tracker's formatting/appending, not reimplement it.
    """
    line_parts = []
    if priority:
        line_parts.append("({})".format(priority.upper()))
    line_parts.append(date or datetime.date.today().isoformat())
    line_parts.append(title)
    line_parts.append("hash:{}".format(issue_hash))
    if project:
        line_parts.append(project if project.startswith('+') else "+{}".format(project))
    if context:
        line_parts.append(context if context.startswith('@') else "@{}".format(context))
    return " ".join(line_parts)

def append_index_line(line):
    """Append one line to the Index and return its 1-based line number.

    ADR-0004: append (never prepend) so existing line numbers stay stable
    for life. A hand-written last line without a trailing newline is not
    glued onto the new line.
    """
    if not line.endswith('\n'):
        line += '\n'
    with open(TODO_FILE, 'r') as f:
        existing = f.read()
    if existing and not existing.endswith('\n'):
        existing += '\n'
    with open(TODO_FILE, 'w') as f:
        f.write(existing + line)
    return existing.count('\n') + 1

def format_archive_line(index_line, date=None):
    """Format an Archive line: 'x <completion-date> <index line>' (ADR-0004)."""
    return "x {} {}".format(date or datetime.date.today().isoformat(), index_line)

def append_done_line(line):
    """Append one line to the Archive (done.txt)."""
    if not line.endswith('\n'):
        line += '\n'
    with open(DONE_FILE, 'a') as f:
        f.write(line)

def _archive_body(line):
    # ADR-0004: an archived line is `x <completion-date> <original line>`.
    # Strip that prefix so the token scan sees the original line's tokens
    # in their normal order. (The Archive's priority token position is a
    # separate, filed bug: hash:b8480e3f.)
    parts = line.split()
    if len(parts) >= 3 and parts[0] == 'x' and DATE_RE.match(parts[1]):
        return ' '.join(parts[2:])
    return line

def _first_date_token(line):
    # ADR-0004 date key: first date token, None when the line has none.
    for part in _archive_body(line).split():
        if DATE_RE.match(part):
            return part
    return None

def _first_priority_token(line):
    # ADR-0004 priority key: first (A)..(Z) token, None when unprioritised.
    for part in _archive_body(line).split():
        if PRIORITY_RE.match(part):
            return part[1]
    return None

def _parse_priority_filter(spec):
    """Parse an ADR-0005 spec into an inclusive (low, high) letter range.

    'C' -> (C, C); 'A-C' -> (A, C); 'C+' -> (A, C); 'C-' -> (C, Z).
    Everything else fails loudly: silent fallbacks would print an empty
    list, which reads as "no matching issues".
    """
    token = spec.strip().upper()
    m = PRIORITY_LETTER_RE.match(token)
    if m:
        return (token, token)
    m = PRIORITY_RANGE_RE.match(token)
    if m:
        low, high = m.group(1), m.group(2)
        if low > high:
            _fail("invalid priority filter '{}': range start {} is below range end {}."
                  " Accepted shapes: {}".format(spec, low, high, PRIORITY_FILTER_SHAPES))
        return (low, high)
    m = PRIORITY_BOUND_RE.match(token)
    if m:
        letter, bound = m.group(1), m.group(2)
        # 'C+' is C and better (A..C); 'C-' is C and worse (C..Z).
        return ('A', letter) if bound == '+' else (letter, 'Z')
    _fail("invalid priority filter '{}': accepted shapes are {}".format(
        spec, PRIORITY_FILTER_SHAPES))

def _matches_priority_filter(letter, bounds):
    if letter is None:
        # Unprioritised lines never match a spec: a missing key is not a
        # priority (ADR-0004).
        return False
    low, high = bounds
    return low <= letter <= high

def _closed_priority_filter_bounds(spec):
    """`list --closed` keeps today's exact-letter -p (ADR-0005 decision 15).

    Archived-line priority is not reliably parseable yet (hash:b8480e3f),
    so a spec that needs the grammar fails loudly instead of silently
    matching nothing.
    """
    token = spec.strip().upper()
    if not PRIORITY_LETTER_RE.match(token):
        _fail("priority filtering on list --closed supports an exact letter only"
              " (got '{}'); the grammar ({}) is blocked on the archived-line"
              " token-order bug hash:b8480e3f".format(spec, PRIORITY_FILTER_SHAPES))
    return (token, token)

def _sort_key(sort_field, line):
    if sort_field == 'date':
        return _first_date_token(line)
    if sort_field == 'priority':
        return _first_priority_token(line)
    raise ValueError("unsupported sort field {!r} (expected 'date' or 'priority')".format(sort_field))

def _sort_rows(args, rows, sort_field, reverse):
    """Order (index, line) rows for display only; the file is not written.

    ADR-0004: rows keep their TRUE Index line number, so sorted output is
    visibly non-monotonic. Rows missing the key form a bucket that stays
    LAST even under --reverse - only the sortable block is reversed.
    `rows` arrives in Index order, and the sort is stable, so ties keep
    Index order in both directions.
    """
    if sort_field is None:
        ordered = list(rows)
        if reverse:
            # No key: --reverse alone means reversed Index order.
            ordered.reverse()
        _trace(args, "list: {} rows in Index order{}".format(
            len(ordered), " (reversed)" if reverse else ""))
        return ordered
    sortable = []
    bucket = []
    for index, line in rows:
        key = _sort_key(sort_field, line)
        if key is None:
            bucket.append((index, line))
        else:
            sortable.append((key, index, line))
    sortable.sort(key=lambda row: row[0], reverse=reverse)
    _trace(args, "list: sorted {} rows by {}{}, {} bucketed last".format(
        len(rows), sort_field, " (reversed)" if reverse else "", len(bucket)))
    return [(index, line) for _key, index, line in sortable] + bucket

def cmd_list(args):
    ensure_environment()
    target_file = DONE_FILE if args.closed else TODO_FILE
    status_label = "Closed" if args.closed else "Open"

    if args.priority_filter is not None:
        # Parsed BEFORE reading rows: a bad spec fails loudly (exit 1),
        # never as an empty list (ADR-0005).
        if args.closed:
            bounds = _closed_priority_filter_bounds(args.priority_filter)
            _trace(args, "list: --closed exact priority filter {}".format(bounds[0]))
        else:
            bounds = _parse_priority_filter(args.priority_filter)
            _trace(args, "list: priority filter {}..{}".format(bounds[0], bounds[1]))
    else:
        bounds = None

    rows = []
    with open(target_file, 'r') as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if args.closed:
                # Legacy path: today's literal '(X)' substring test
                # (ADR-0005 decision 15; hash:b8480e3f).
                if bounds and "({})".format(bounds[0]) not in line:
                    continue
            elif bounds and not _matches_priority_filter(_first_priority_token(line), bounds):
                continue
            rows.append((idx, line))
    rows = _sort_rows(args, rows, args.sort, args.reverse)

    print("\n--- {} Issues ({}) ---\n".format(status_label, target_file))
    for idx, line in rows:
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
    # Explicit Hash Form (ADR-0002): copy/paste target for other commands.
    print("Hash Token : hash:{}".format(full_hash))
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

DASH_MARKER = '-'

def cmd_comment(args):
    ensure_environment()
    # nargs='+' means shell word-splitting (e.g. `cat f` unquoted) shows
    # up here as a list instead of an argparse usage error (hash:d2b6b1cf
    # case 2). Fail loudly with a hint rather than silently joining; see
    # hash:6e4084b4 for the deferred join idea. Programmatic callers may
    # pass a plain string (py2 unicode / py3 str); anything else fails
    # fast with actual vs expected.
    if isinstance(args.text, type(u'')):
        args.text = [args.text]
    if not isinstance(args.text, list):
        raise AssertionError("expected comment text as text or list of text, "
                             "got {} (type {})".format(args.text, type(args.text).__name__))
    if len(args.text) < 1:
        raise AssertionError("expected 1+ comment text argument(s), got 0")
    if len(args.text) > 1:
        raise AssertionError("comment takes one text argument; got {} "
                             "arguments (shell word-splitting?). Quote the text "
                             "or pipe it via '-'; joining extras is deferred "
                             "(hash:6e4084b4)".format(len(args.text)))
    args.text = args.text[0]
    full_hash = resolve_identifier(args, args.identifier)

    # Dash Marker (docs/plans/comment-stdin.md): '-' as the text arg
    # means read the comment body from Standard Input. Conflict check
    # BEFORE any side effect: no comment file is created on failure.
    stdin_piped = not sys.stdin.isatty()
    if stdin_piped and args.text not in (None, DASH_MARKER):
        _fail("both a text argument ('{}') and piped stdin given; give "
              "one or the other".format(args.text))
    if args.text == DASH_MARKER:
        # Fail fast rather than block on a TTY stdin (e.g. interactive
        # shell with no pipe).
        if sys.stdin.isatty():
            _fail("Dash Marker '-' given but stdin is a terminal; pipe "
                  "the comment body, e.g. cat file | todo.py comment "
                  "<id> -")
        # Read bytes, write binary: byte fidelity, no text-mode
        # translation, no encoding validation. Empty stdin is an error.
        data = read_stdin_bytes()
        if not data:
            _fail("no stdin content (Dash Marker '-' expects a piped body)")
        body = data
    else:
        body = args.text.encode('utf-8')

    issue_dir = _ensure_issue_dir(full_hash)
    comments_dir = os.path.join(issue_dir, 'comments')
    if not os.path.exists(comments_dir):
        os.makedirs(comments_dir)

    # UTC timestamp, seconds precision, one format, no collision handling.
    timestamp = _utcnow().strftime('%Y%m%d_%H%M%S')
    comment_filename = "{}.md".format(timestamp)
    comment_path = os.path.join(comments_dir, comment_filename)

    with open(comment_path, 'wb') as f:
        f.write(body)

    print("Added comment to {} as {}".format(full_hash, comment_filename))

def _warn_renumbered(lines_before, n):
    # Closing removes a line, so every later Index line number shifts up
    # by one. Warn once, only when the shift actually happened (closing
    # the last line renumbers nothing). ADR-0004 amendment.
    if n <= len(lines_before) - 1:
        print("Note: {} open line(s) renumbered (later line numbers shifted up by one).".format(len(lines_before) - n))

def cmd_close(args):
    ensure_environment()
    # Close-only exception for no-hash manual lines (ADR-0002): resolve
    # by line number first; if the line has no hash: token, mint a hash
    # at close time so the archived line is addressable in done.txt.
    raw_line = _in_range_line(args.identifier)
    if raw_line and not _hash_of_line(raw_line):
        title = _title_from_line(raw_line)
        full_hash = mint_hash_unique(title, _all_hash_tokens())
        minted = format_archive_line("{} hash:{}".format(raw_line, full_hash)) + "\n"
        with open(TODO_FILE, 'r') as f:
            lines = f.readlines()
        n = int(args.identifier)
        new_todo_lines = lines[:n - 1] + lines[n:]
        with open(TODO_FILE, 'w') as f:
            f.writelines(new_todo_lines)
        append_done_line(minted)
        _trace(args, "close: minted hash {} for no-hash line {}".format(full_hash, n))
        print("Closed and archived issue [{}] (hash minted at close)".format(full_hash))
        _warn_renumbered(lines, n)
        return
    full_hash = resolve_identifier(args, args.identifier)

    # Read todo.txt, find line, remove, and append to done.txt with 'x YYYY-MM-DD'
    with open(TODO_FILE, 'r') as f:
        lines = f.readlines()

    new_todo_lines = []
    matched_line = None
    matched_line_no = None
    today = datetime.date.today().isoformat()

    for line_no, line in enumerate(lines, 1):
        if "hash:{}".format(full_hash) in line:
            # Format closed line: x YYYY-MM-DD <original_line>
            matched_line = format_archive_line(line.strip(), today) + "\n"
            matched_line_no = line_no
        else:
            new_todo_lines.append(line)

    if not matched_line:
        print("Error: Issue hash '{}' not found in active {} (might already be closed).".format(full_hash, TODO_FILE), file=sys.stderr)
        sys.exit(1)

    with open(TODO_FILE, 'w') as f:
        f.writelines(new_todo_lines)

    append_done_line(matched_line)

    print("Closed and archived issue [{}]".format(full_hash))
    _warn_renumbered(lines, matched_line_no)

# ---------------------------------------------------------------------------
# Mint: bestow a hash on Unhashed Lines (hand-written Index lines)
#
# ADR-0003. 'hash' repairs todo.txt only; done.txt backfill is deferred.
# The minted token is APPENDED at the end of the line so the derived title
# (everything before the hash: token) does not change and existing
# title-substring identifiers keep resolving.
# ---------------------------------------------------------------------------

def _read_raw_lines(filepath):
    # newline='' + binary-safe join: a rewrite is byte-identical apart
    # from the appended tokens (CRLF worktrees stay CRLF). Invalid UTF-8
    # fails loudly rather than silently mangling bytes.
    with io.open(filepath, 'r', encoding='utf-8', newline='') as f:
        raw = f.read()
    if not raw:
        return []
    parts = raw.split('\n')
    lines = ["{}\n".format(p) for p in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines

def _write_raw_lines(filepath, lines):
    with io.open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(''.join(lines))

def _all_hash_tokens():
    taken = set()
    for filepath in (TODO_FILE, DONE_FILE):
        if not os.path.exists(filepath):
            continue
        with io.open(filepath, 'r', encoding='utf-8', newline='') as f:
            for line in f:
                h = _hash_of_line(line)
                if h:
                    taken.add(h.lower())
    return taken

def _unhashed_line_numbers(lines):
    # Non-blank lines with no hash: token, 1-based like `list` numbering.
    return [n for n, line in enumerate(lines, 1)
            if line.strip() and not _hash_of_line(line)]

def _mint_targets(args, lines):
    """Return the 1-based line numbers to mint (ADR-0003)."""
    if args.identifier is None:
        return _unhashed_line_numbers(lines)
    token = args.identifier
    if DIGITS_RE.match(token):
        n = int(token)
        if 1 <= n <= len(lines):
            raw = lines[n - 1].strip()
            if not raw:
                _fail("line {} in {} is blank".format(token, TODO_FILE))
            existing = _hash_of_line(raw)
            if existing:
                _fail("line {} in {} already has hash:{}".format(token, TODO_FILE, existing))
            return [n]
        _trace(args, "hash: line {} out of range; trying title".format(token))
    matches = [(n, line) for n, line in enumerate(lines, 1)
               if line.strip() and not _hash_of_line(line)
               and token.lower() in _title_from_line(line.strip()).lower()]
    if not matches:
        _fail("no Unhashed Line matching '{}' in {}".format(token, TODO_FILE))
    if len(matches) > 1:
        _fail_ambiguous(token, [], [{'title': _title_from_line(l.strip()), 'line': l.strip()}
                                    for _n, l in matches])
    return [matches[0][0]]

def cmd_hash(args):
    ensure_environment()
    lines = _read_raw_lines(TODO_FILE)
    targets = _mint_targets(args, lines)
    if not targets:
        print("nothing to mint ({} has no Unhashed Lines)".format(TODO_FILE))
        return
    taken = _all_hash_tokens()
    minted = []
    for n in targets:
        line = lines[n - 1]
        body = line.rstrip('\r\n')
        eol = line[len(body):]
        title = _title_from_line(body)
        new_hash = mint_hash_unique(title, taken)
        taken.add(new_hash)
        lines[n - 1] = "{} hash:{}{}".format(body, new_hash, eol)
        minted.append((n, new_hash, title))
        _trace(args, "hash: line {} -> {}".format(n, new_hash))
    if not minted:
        print("nothing to mint ({} has no Unhashed Lines)".format(TODO_FILE))
        return
    _write_raw_lines(TODO_FILE, lines)
    for n, new_hash, title in minted:
        print("line {}: hash:{} <- {}".format(n, new_hash, title))
    print("Minted {} hash(es) in {}".format(len(minted), TODO_FILE))

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

def _editor_launch_disabled():
    # Non-empty TODO_NO_EDITOR suppresses the editor launch (batch/CI).
    # No value parsing: '0' or 'false' also suppress; unset to re-enable.
    return bool(os.environ.get('TODO_NO_EDITOR'))

def cmd_edit(args):
    # Checked BEFORE any side effect: a suppressed launch must not create
    # a Details Directory or a bootstrap issue.md.
    if _editor_launch_disabled():
        _fail("editor launch disabled by $TODO_NO_EDITOR"
              " (unset it to launch an editor)")
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
    # ADR-0017: store location. Flags override env vars (TODO_TRACKER_DIR /
    # TODO_FILE), which override the defaults. See apply_store().
    common.add_argument('--dir', default=None, metavar='DIR',
                        help='Store directory (todo.txt, done.txt, .issues/ '
                             'live here); env TODO_TRACKER_DIR overrides')
    common.add_argument('--file', default=None, metavar='FILE',
                        help='Todo index file name or full path; a full path '
                             'implies its parent dir for the whole bundle; '
                             'env TODO_FILE overrides')

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
    parser_list.add_argument('-p', '--priority-filter', dest='priority_filter', default=None,
                             metavar='SPEC',
                             help='Filter by priority: A, A-C, C+, C- (exact letter only with --closed)')
    # ADR-0004: view flags only; the Index file is never rewritten.
    parser_list.add_argument('--sort', choices=['date', 'priority'], default=None,
                             help='Sort the displayed rows by date or priority (file order untouched)')
    parser_list.add_argument('-r', '--reverse', action='store_true', default=False,
                             help='Reverse the displayed order (with --sort: the sortable block only)')

    # show
    parser_show = subparsers.add_parser('show', parents=[common], help='Inspect issue details, description, and comments')
    parser_show.add_argument('identifier', help='Issue identifier: hash:<hex>, line number, hash prefix, or title substring')

    # comment
    parser_comment = subparsers.add_parser('comment', parents=[common], help='Add a timestamped comment to an issue')
    parser_comment.add_argument('identifier', help='Issue identifier: hash:<hex>, line number, hash prefix, or title substring')
    parser_comment.add_argument('text', nargs='+', help="Comment text, or '-' to read the comment body from stdin")

    # close
    parser_close = subparsers.add_parser('close', parents=[common], help='Close an issue and archive it to done.txt')
    parser_close.add_argument('identifier', help='Issue identifier: hash:<hex>, line number, hash prefix, or title substring')

    # edit
    parser_edit = subparsers.add_parser('edit', parents=[common], help='Open issue description in $EDITOR')
    parser_edit.add_argument('identifier', help='Issue identifier: hash:<hex>, line number, hash prefix, or title substring')

    # hash (mint hashes for Unhashed Lines)
    parser_hash = subparsers.add_parser('hash', parents=[common],
                                        help='Mint hashes for hand-written todo.txt lines that have none')
    parser_hash.add_argument('identifier', nargs='?', default=None,
                             help='Optional: line number or title substring; omit for every Unhashed Line')

    # 'help' is not a subcommand: behave as if --help had been issued
    # (hash:eb1deb21). Intercepted before parse_args so 'todo.py help'
    # prints the same help as 'todo.py --help', and 'todo.py help <cmd>'
    # prints that subcommand's help. Unknown topics fail loudly.
    if len(sys.argv) > 1 and sys.argv[1] == 'help':
        if len(sys.argv) == 2:
            parser.print_help()
            sys.exit(0)
        if len(sys.argv) > 3:
            print("Error: help takes at most one topic: {}".format(
                ', '.join(subparsers.choices)), file=sys.stderr)
            sys.exit(1)
        topic = sys.argv[2]
        if topic in subparsers.choices:
            subparsers.choices[topic].print_help()
            sys.exit(0)
        print("Error: unknown help topic '{}': choose from {}".format(
            topic, ', '.join(subparsers.choices)), file=sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    # ADR-0017: apply store location (flags > env vars > defaults) before
    # any command touches the store.
    apply_store(dir_value=args.dir, file_value=args.file)

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
    elif args.command == 'hash':
        cmd_hash(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
