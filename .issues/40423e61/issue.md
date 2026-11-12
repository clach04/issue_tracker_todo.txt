Currently --dir/--file are only parsed on each subcommand (shared argparse parent), so they must come AFTER the subcommand: `todo.py list --dir X`. Users expect global-option position to work as well: `todo.py --file tmp/todo.txt list` fails (unrecognized argument at the top-level parser).

Spawn source: user quick-test of ADR-0017 implementation (issue hash:9efddab9, now closed). Workaround available: env vars work anywhere, e.g. `TODO_FILE=tmp/todo.txt ./todo.py list`.

Approach: add --dir/--file to the top-level parser as well; subcommand occurrence should win over the top-level one (most specific wins). Check the `help` pre-interception path in main() for the same support. webui/md2todo unaffected (no subcommands). Reference: docs/adr/0017-configurable-store-location.md.