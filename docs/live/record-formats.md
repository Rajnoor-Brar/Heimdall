---
id: live-record-formats
summary: record files carry a format version, and heimdall records upgrade brings old ones to it
affects: provenance, plots
issue: I-28
---

**Now holds:** `points.json`, `provenance.json` and `identity.json` have `"format": 1` first at top level, and `plot.toml` has `format = 1` in `[source]` (`record.FORMAT`). A file without the key is format 0, today's before the key, and is read as it always was. A file of a newer format is refused by the readers (`record.check_format`: "this record is format N; this Heimdall reads up to 1", hint: update Heimdall). `identity.json`'s `format` is outside the hashed parts: the identity is the hash of the file without it, `--why` ignores it, and the golden identity file is unchanged. `heimdall records upgrade [--dry-run] [A[/E[/R]]]` lists the record files below format 1 and, without `--dry-run`, gives each the key, a copy of it beside it first (`<name>.bak`, then `.bak2`, …); it is refused while a job of the work dir is going. It counts the layout moves of `heimdall migrate --layout` and leaves them to it.

**No longer holds:** `identity.json` being exactly the identity's parts; a reader that ignores which version wrote a record.

**Decisions:** the version is one number for the record files together, not one each. `records upgrade` stamps files only: the layout moves are staged and a work dir's own, so `migrate --layout` stays their command. Every reader that acts on a record checks its format: `results.load`, `plot` (the manifest), `plotdoc.load`, `from_manifest`, the events read, `record.why`, `diffcmd`, and in `cli.py` `reproduce`, `migrate --plot-docs` and `--snapshot` (`record.check_format`). `heimdall show` does not: it prints what a record claims, a newer one too.

**Stable pages need:** `stable/internals/provenance.md` (the files, `format`, and identity.json's key), `stable/internals/layout.md` or the CLI guide (`records upgrade`).
