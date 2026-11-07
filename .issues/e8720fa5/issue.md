Observed 2026-11-07 while adding the "How the hash is created" section to README.md.

1. Section heading reads "## todo.txt key balue pairs" - "balue" should be "value".
2. In the Priority bullet, the bold span is malformed: "**Priority `(A)` through `(Z)**`" - the backtick/bold order is wrong, so it renders literally instead of as bold `(Z)`.

Repro: open README.md (line ~28 and ~34). Fix is text-only; no code or test changes.

Related: hash documentation issue closed as hash:5c2000ea, hash mint 2026-11-07.