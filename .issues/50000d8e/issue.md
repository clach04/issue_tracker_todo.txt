`list --sort date|priority` shipped without a short flag: only `--sort` plus `--reverse`/`-r`. A `-s` for `--sort` was considered and deliberately deferred (docs/plans/list-sort-and-priority-filter.md decision 4) rather than rejected.

Why deferred: `-s` was never argued for; the session wanted to see real usage first. Note the collision risk with any future `--status` flag (the POC spec in docs/plans/done/initial.md used `--status <open|closed>`; today that is `--closed`).

Action: after some real use of `--sort`, decide whether `-s` earns its place. If it does, add it in `main()` next to `-r` and document it in README.