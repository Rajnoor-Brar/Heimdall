# {{name}} — a Heimdall work dir

- `configs/` and `modules/` are the user's: change them only when asked, and show the diff.
- `results/`, `output/` and `build/` are made by `hep run` and `hep build`. Never write into
  `results/` from a test or a script: use a scratch work dir (`hep setup <scratch>`).
- The manual is `$HEP/docs/README.md` (Heimdall's, `hep where --hep`). Read the relevant page before
  writing a run TOML; `hep explain <key>` and `hep check` say what a key means and whether a file is valid.
- Paths in configs: `{work}` is this folder, `{hep}` is Heimdall.
- Commit by path (`git add <files>`), never `git commit -a`.
