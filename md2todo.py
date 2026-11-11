#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
md2todo.py - import a GFM task list into the tracker (ADR-0006).

Separate tool, NOT a `todo.py` subcommand: import is a one-shot
conversion, not a tracker operation. `todo.py` is imported as a library
for minting, line formatting and appending (format_index_line,
mint_hash_unique, _all_hash_tokens, append_index_line, append_done_line).

v1 model (plan docs/plans/gfm-import.md, moved to docs/plans/done/):
  - one Issue per TOP-LEVEL checklist item;
  - nested items are stored verbatim in the parent issue.md (original
    lines incl. the checkbox line itself, no dedent);
  - checked items import closed, except a checked item with any unchecked
    descendant imports open and records `originally: - [x]`.
"""
from __future__ import print_function, unicode_literals

import argparse
import hashlib
import io
import os
import re
import sys

import todo

TITLE_LIMIT = 200
ELLIPSIS = '...'
NOTES_HEADING = '## Notes'
ORIGINALLY_CHECKED_LINE = 'originally: - [x]'
# Same retry budget as todo.mint_hash_unique (todo.py, ADR-0003).
MINT_ATTEMPTS = 10

# Checkbox line: list marker (-, *, +, or ordered N. / N)) then [ ]/[x]/[X].
# Group 1 = indentation, 2 = checkbox state, 3 = text after the checkbox.
ITEM_RE = re.compile(r'^([ \t]*)(?:[-*+]|\d+[.)])[ \t]+\[([ xX])\](?:[ \t]+(.*))?$')
# Fenced code block marker (three or more backticks or tildes), any info string.
FENCE_RE = re.compile(r'^[ \t]*(`{3,}|~{3,})')

TAB_WIDTH = 4

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _read_lines(path):
    """Read the source file as a list of lines with EOL stripped."""
    with io.open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    if not raw:
        return []
    lines = raw.split('\n')
    if lines[-1] == '':
        lines.pop()
    return [line[:-1] if line.endswith('\r') else line for line in lines]

def _fenced_flags(lines):
    """Per-line flag: True when the line is inside (or opens) a code fence.

    Fenced content is never a Checklist Item; it is Content verbatim.

    Inline fences (open marker at line start + close marker at line end,
    e.g. "```[tool] call {...}]}]}```") are self-contained: they close
    on the SAME line. Not standard GFM (the closing fence must be alone
    on its line there), but seen in the wild - Python-string-literal
    style. Without this, the fence stays open until the next fence
    marker on its own line, swallowing every following item until that
    line (hash:4ae2da8b).
    """
    flags = []
    open_fence = None
    for line in lines:
        m = FENCE_RE.match(line)
        marker = m.group(1)[0] if m else None
        if open_fence is None and m:
            stripped = line.strip()
            if stripped != m.group(1) and stripped.endswith(marker * 3):
                # Inline fence: marker at line start + close marker run
                # (3+ of the same char) at line end. The line is fenced
                # and closes on the SAME line; no fence state is opened.
                flags.append(True)
                continue
        if open_fence is None:
            flags.append(m is not None)
            if m:
                open_fence = marker
        else:
            flags.append(True)
            if m and marker == open_fence:
                open_fence = None
    return flags

def _indent_width(text):
    # Tabs count as TAB_WIDTH columns; only relative order matters, and a
    # tab always nests deeper than the same number of spaces.
    return sum(TAB_WIDTH if ch == '\t' else 1 for ch in text)

def parse_items(lines):
    """Return Checklist Items in file order, fences excluded."""
    fenced = _fenced_flags(lines)
    items = []
    for index, line in enumerate(lines):
        if fenced[index]:
            continue
        m = ITEM_RE.match(line)
        if not m:
            continue
        text = (m.group(3) or '').strip()
        items.append({
            'index': index,             # 0-based source line
            'line': index + 1,          # 1-based source line (for messages)
            'indent': _indent_width(m.group(1)),
            'checked': m.group(2) != ' ',
            'title': text,              # verbatim: no metadata extraction
            'skip': not text,           # empty checkbox -> skipped
        })
    return items

def build_tree(items):
    """Nest items by indentation; return the root nodes.

    Indentation is a hint: an indented item with no parent above it is a
    root (malformed file, real task).
    """
    roots = []
    stack = []
    for item in items:
        node = {}
        node.update(item)
        node['children'] = []
        node['parent'] = None
        while stack and node['indent'] <= stack[-1]['indent']:
            stack.pop()
        if stack:
            node['parent'] = stack[-1]
            stack[-1]['children'].append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots

def promote_issues(roots, warnings):
    """Return the top-level Issues after skipping empty Checklist Items.

    An empty item with children is skipped, and its children are PROMOTED
    to top-level Issues (they are real work and must not be lost).
    """
    issues = []

    def walk(nodes):
        for node in nodes:
            if node['skip']:
                warnings.append(node)
                walk(node['children'])
            else:
                issues.append(node)

    walk(roots)
    return issues

def _last_descendant_index(node, lines, fenced):
    """Last 0-based line index belonging to node's subtree.

    Checkbox children are walked as before. Non-checkbox, non-fenced
    lines indented deeper than the nearest preceding item belong to that
    item too (continuation / note lines, ADR-0006): without this the
    subtree ends at the item's own line and the notes leak into the next
    item's preceding content.
    """
    last = _last_item_or_continuation_index(node['index'], lines, fenced)
    for child in node['children']:
        last = max(last, _last_descendant_index(child, lines, fenced))
    return last

def _last_item_or_continuation_index(index, lines, fenced):
    """Scan forward from item `index` while lines continue that item.

    A line continues the item when it is fenced, blank, or indented at
    least one column deeper than the item's own indent. Scanning stops at
    the first line shallower than or equal to the item's indent that is
    neither blank nor fenced (a sibling or an outdented block), or at EOF.
    Blank lines inside a run are kept optimistically; a trailing blank run
    is trimmed later by _trim_blank. Fenced lines always continue: a code
    block under an item may contain outdented content, and a fence whose
    content is indented deeper than the next item's indent must not be
    split between two items.
    """
    last = index
    item_indent = None
    for i in range(index + 1, len(lines)):
        line = lines[i]
        if fenced[i]:
            last = i
            continue
        if not line.strip():
            last = i
            continue
        indent = _indent_width(line[:len(line) - len(line.lstrip(' \t'))])
        if item_indent is None:
            item_indent = _item_indent_from_lines(index, lines, fenced)
        if indent > item_indent:
            last = i
            continue
        break
    return last

def _item_indent_from_lines(index, lines, fenced):
    """The item's own indent width (ITEM_RE captured it at parse time)."""
    m = ITEM_RE.match(lines[index])
    assert m is not None, "line {} is not a checklist item: {!r}".format(index + 1, lines[index])
    return _indent_width(m.group(1))

def _has_unchecked_descendant(node):
    """True when any real descendant is unchecked (empty items are skipped)."""
    for child in node['children']:
        if child['skip']:
            if _has_unchecked_descendant(child):
                return True
            continue
        if (not child['checked']) or _has_unchecked_descendant(child):
            return True
    return False

# ---------------------------------------------------------------------------
# Content regions
# ---------------------------------------------------------------------------

def _trim_blank(lines):
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]

def _dedent(lines):
    """Remove the common leading whitespace run (blank lines stay empty)."""
    indents = []
    for line in lines:
        if line.strip():
            indents.append(len(line) - len(line.lstrip(' \t')))
    cut = min(indents) if indents else 0
    out = []
    for line in lines:
        if not line.strip():
            out.append('')
            continue
        assert not line[:cut].strip(), "dedent cut {} splits text on {!r}".format(cut, line)
        out.append(line[cut:])
    return out

def _region(lines, start, end, skip_lines):
    """Trimmed, dedented content for the 0-based half-open range [start, end).

    `skip_lines` holds 0-based indexes of skipped empty items: they are
    not Content, so their lines are dropped from content regions (inside
    a nested block they stay verbatim - that is a slice, not a region).
    """
    region = [lines[i] for i in range(start, end) if i not in skip_lines]
    return _dedent(_trim_blank(region))

# ---------------------------------------------------------------------------
# Titles and issue.md assembly
# ---------------------------------------------------------------------------

def truncate_title(title):
    """Cut an overlong title to TITLE_LIMIT chars at a word boundary.

    Three ASCII dots are appended, so the result can be up to
    TITLE_LIMIT + 3 chars. A single long word is hard-cut.
    """
    if len(title) <= TITLE_LIMIT:
        return title
    head = title[:TITLE_LIMIT]
    if not title[TITLE_LIMIT].isspace():
        cut = head.rfind(' ')
        if cut > 0:
            head = head[:cut]
    return head.rstrip() + ELLIPSIS

def build_issue_body(title, originally_checked, verbatim_block, preceding,
                     notes):
    """Assemble issue.md text, or None when there is nothing to store.

    `verbatim_block` is the item's ORIGINAL source lines (the `- [x]`
    line itself plus everything through its subtree), never dedented.
    When present it leads the body and NO '# title' header is emitted:
    the block's first line is the title, and the original block must be
    readable exactly as authored, indentation included (ADR-0006
    amendment 2026-11-08b; duplicating the title/bullet is accepted).

    A block that carries nothing beyond the item's own checkbox line is
    not content (a bare duplicate of the Index line would give every
    contentless issue a Details Directory).

    issue.md exists only for actual content (verbatim block, preceding
    content, or trailing notes). An overlong title is content too:
    truncation makes the Index line lossy, so the full title must live
    somewhere.
    """
    overlong = len(title) > TITLE_LIMIT
    block = list(verbatim_block or [])
    # The bare checkbox line counts as content only when the issue has
    # other content too (never alone: that is a pure Index duplicate).
    extra_block = any(line.strip() for line in block[1:])
    if not (extra_block or preceding or notes or overlong):
        return None
    parts = []
    if block:
        parts.append('\n'.join(block))
    elif not overlong:
        # No original lines (defensive; the caller always passes the
        # item's own line): fall back to a header so issue.md still
        # names the issue.
        parts.append('# {}'.format(title))
    if overlong:
        parts.append(title)
    if originally_checked:
        parts.append(ORIGINALLY_CHECKED_LINE)
    if preceding:
        parts.append('\n'.join(preceding))
    if notes:
        parts.append('{}\n\n{}'.format(NOTES_HEADING, '\n'.join(notes)))
    return '\n\n'.join(parts) + '\n'

# ---------------------------------------------------------------------------
# Plan (pure: no writes)
# ---------------------------------------------------------------------------

def build_plan(lines):
    """Return (issues, warnings) for the source lines.

    Content attribution (plan "Content attribution"):
      - before the first item           -> that item's preceding content;
      - after issue A's subtree,
        before issue B                  -> B's preceding content;
      - inside an issue's subtree       -> verbatim in its nested block;
      - after the last item's subtree   -> last issue's issue.md, `## Notes`.
    """
    items = parse_items(lines)
    if not items:
        return [], []
    fenced = _fenced_flags(lines)
    warnings = []
    issues = promote_issues(build_tree(items), warnings)
    skip_lines = set(node['index'] for node in warnings)
    if not issues:
        return [], warnings
    plan = []
    prev_body_end = 0
    for pos, node in enumerate(issues):
        next_start = issues[pos + 1]['index'] if pos + 1 < len(issues) else len(lines)
        # The subtree must not swallow the content that belongs to the
        # NEXT issue, so its end is capped by that issue's line.
        body_end = min(_last_descendant_index(node, lines, fenced),
                       next_start - 1) + 1
        preceding = _region(lines, prev_body_end, node['index'], skip_lines)
        # The item's ORIGINAL source lines: the checkbox line itself plus
        # everything through its subtree, verbatim (no dedent). The title
        # and bullet are duplicated on purpose (ADR-0006 amendment
        # 2026-11-08b): the reader sees the block exactly as authored.
        verbatim_block = lines[node['index']:body_end]
        while verbatim_block and not verbatim_block[-1].strip():
            verbatim_block.pop()
        notes = []
        if pos + 1 == len(issues):
            notes = _region(lines, body_end, len(lines), skip_lines)
        unchecked_descendant = _has_unchecked_descendant(node)
        plan.append({
            'line': node['line'],
            'title': node['title'],
            'index_title': truncate_title(node['title']),
            'checked': node['checked'],
            'originally_checked': node['checked'] and unchecked_descendant,
            'open': (not node['checked']) or unchecked_descendant,
            'issue_md': build_issue_body(node['title'],
                                         node['checked'] and unchecked_descendant,
                                         verbatim_block, preceding, notes),
        })
        prev_body_end = body_end
    return plan, warnings

# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _issue_md_path(issue_hash):
    return os.path.join(todo.ISSUES_DIR, issue_hash, 'issue.md')

def _write_issue_md(issue_hash, text):
    issue_dir = os.path.join(todo.ISSUES_DIR, issue_hash)
    if not os.path.exists(issue_dir):
        os.makedirs(issue_dir)
    with io.open(_issue_md_path(issue_hash), 'w', encoding='utf-8') as f:
        f.write(text)

def _next_index_line_number():
    """Predict the line append_index_line would use (ADR-0004 append)."""
    if not os.path.exists(todo.TODO_FILE):
        return 1
    with open(todo.TODO_FILE, 'r') as f:
        existing = f.read()
    if existing and not existing.endswith('\n'):
        existing += '\n'
    return existing.count('\n') + 1

def _generate_title_hash(title):
    """Deterministic 8-hex hash from the title ALONE (no timestamp).

    md2todo-only (ADR-0006 amendment 2026-11-08c): re-importing the same
    file twice must produce the same hashes, so an import can be debugged
    with git checkout / re-runs instead of hand-editing todo.txt.
    todo.py's add/hash/close stay timestamp-based: interactive mints
    SHOULD differ even for identical titles.
    """
    hasher = hashlib.sha256()
    hasher.update(title.encode('utf-8'))
    return hasher.hexdigest()[:8]


def run_import(plan, args, dry_run):
    """Mint, write issue.md / Index / Archive lines; return the counters."""
    taken = todo._all_hash_tokens()
    preexisting = set(taken)
    next_line = _next_index_line_number()
    counts = {'open': 0, 'closed': 0, 'issue_md': 0}
    for item in plan:
        # Hash is minted from the TRUNCATED title: the Index line is the
        # source of truth (ADR-0006). Deterministic (title-only, no
        # timestamp, md2todo amendment 2026-11-08c) so re-imports after a
        # cleanup reproduce the same hashes.
        #
        # A base hash already in the tracker means this title was
        # imported before: FAIL LOUDLY instead of silently minting a
        # different hash (that would break reproducibility - the whole
        # point of the amendment). The user cleans up (git checkout) or
        # renames the item. Duplicates WITHIN one file get the
        # deterministic '#N' suffix retry.
        candidate = _generate_title_hash(item['index_title'])
        if candidate in preexisting:
            todo._fail("title {!r} is already in the tracker as hash:{};"
                       " remove that issue first or rename the item"
                       .format(item['index_title'], candidate))
        attempts = 0
        while candidate in taken:
            attempts += 1
            if attempts > MINT_ATTEMPTS:
                todo._fail("could not mint a unique hash for {!r} after {} attempts".format(
                    item['index_title'], MINT_ATTEMPTS))
            candidate = _generate_title_hash('{} #{}'.format(item['index_title'], attempts))
        issue_hash = candidate
        taken.add(issue_hash)
        index_line = todo.format_index_line(item['index_title'], issue_hash,
                                            priority=args.priority,
                                            project=args.project,
                                            context=args.context)
        if dry_run:
            if item['open']:
                print("would create (open) line {}: {}".format(next_line, item['index_title']))
            else:
                print("would create (closed) -> {}: {}".format(todo.DONE_FILE, item['index_title']))
            if item['issue_md'] is not None:
                print("would create issue.md: {}".format(_issue_md_path(issue_hash)))
            if item['originally_checked']:
                print("  (would record '{}' in issue.md)".format(ORIGINALLY_CHECKED_LINE))
            if item['open']:
                next_line += 1
        else:
            if item['issue_md'] is not None:
                _write_issue_md(issue_hash, item['issue_md'])
                print("wrote {}".format(_issue_md_path(issue_hash)))
            if item['open']:
                number = todo.append_index_line(index_line)
                print("created (open) line {}: '{}' hash:{}".format(
                    number, item['index_title'], issue_hash))
            else:
                todo.append_done_line(todo.format_archive_line(index_line))
                print("created (closed) -> {}: '{}' hash:{}".format(
                    todo.DONE_FILE, item['index_title'], issue_hash))
        counts['open' if item['open'] else 'closed'] += 1
        if item['issue_md'] is not None:
            counts['issue_md'] += 1
    return counts

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog='md2todo.py',
        description='Import a GFM task list into the tracker (ADR-0006)')
    parser.add_argument('input', help='GFM markdown file with a task list (exactly one)')
    # ADR-0017: store location. Flags override env vars (TODO_TRACKER_DIR /
    # TODO_FILE), which override the defaults. See todo.apply_store().
    parser.add_argument('--dir', default=None, metavar='DIR',
                        help='Store directory (todo.txt, done.txt, .issues/ '
                             'live here); env TODO_TRACKER_DIR overrides')
    parser.add_argument('--file', default=None, metavar='FILE',
                        help='Todo index file name or full path; a full path '
                             'implies its parent dir for the whole bundle; '
                             'env TODO_FILE overrides')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        help='Print the plan and the paths; write nothing')
    parser.add_argument('--flatten', action='store_true', default=False,
                        help='Reserved for full recursive nesting; fails loudly in v1')
    parser.add_argument('-p', '--priority', default=None, metavar='A',
                        help='Priority letter applied to EVERY imported issue')
    parser.add_argument('--project', default=None,
                        help='Project tag applied to EVERY imported issue')
    parser.add_argument('--context', default=None,
                        help='Context tag applied to EVERY imported issue')
    parser.add_argument('--verbose', action='store_true', default=False,
                        help='Trace-level output for major steps')
    return parser

def _report_warnings(warnings, path):
    for node in warnings:
        print("warning: skipped empty checklist item at line {} of {}".format(
            node['line'], path), file=sys.stderr)
    if warnings:
        print("warning: skipped {} empty checklist item(s);"
              " any children were promoted to top-level issues".format(len(warnings)),
              file=sys.stderr)

def main(argv=None):
    args = build_parser().parse_args(argv)
    # ADR-0017: resolve store location (flags > env vars > defaults)
    # before touching the store.
    todo.apply_store(dir_value=args.dir, file_value=args.file)
    if args.flatten:
        # The name is locked by ADR-0006 so a later version cannot be
        # forced to pick a different flag.
        todo._fail("--flatten is not implemented yet (v1 imports top-level items only)")
    if not os.path.exists(args.input):
        todo._fail("file not found: {}".format(args.input))
    lines = _read_lines(args.input)
    todo._trace(args, "md2todo: read {} line(s) from {}".format(len(lines), args.input))
    plan, warnings = build_plan(lines)
    if not plan:
        _report_warnings(warnings, args.input)
        todo._fail("no checklist items found in {}".format(args.input))
    _report_warnings(warnings, args.input)
    todo._trace(args, "md2todo: {} issue(s) planned, dry_run={}".format(len(plan), args.dry_run))
    if not args.dry_run:
        todo.ensure_environment()
    counts = run_import(plan, args, args.dry_run)
    verb = "would import" if args.dry_run else "imported"
    print("{} {} issue(s): {} open, {} closed; {} issue.md file(s)".format(
        verb, len(plan), counts['open'], counts['closed'], counts['issue_md']))
    if args.dry_run:
        print("note: hashes are deterministic (title-only); re-importing"
              " unchanged content fails loudly until the tracker is"
              " cleaned up (ADR-0006 amendment 2026-11-08c)")

if __name__ == '__main__':
    main()
