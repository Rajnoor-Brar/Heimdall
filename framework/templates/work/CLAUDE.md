# {{name}} — a Heimdall work dir

Run `heimdall context` first: it says how to work here, and what Heimdall is, for the version this shell uses.

- `heimdall explain <key>` says what a key means; `heimdall check` whether a file is valid.
- `configs/` and `modules/` are the user's: change them only when asked, and show the diff.
- Never write into `results/` from a test or a script: use a scratch work dir (`heimdall setup <scratch>`).
- Commit by path (`git add <files>`), never `git commit -a`.
