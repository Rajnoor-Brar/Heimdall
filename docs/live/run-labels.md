---
id: live-run-labels
summary: a Run's tag is one of its labels: key=value words from heimdall tag, in the tag file's TOML, each an across axis @key
affects: plots
issue: I-126
---

**Now holds:** a Run's tag file (`records/<A>/<E>/<R>/tag`) is TOML: `format = 1` and a `[labels]` table. `tag` is one label; the others are `key = "value"` (`shower = "new"`). A key is a lower-case letter then lower-case letters, digits and `_` (30 at most), never `run`, `events` or `configuration` (across attributes already); a value is a tag's (a letter or digit, then letters, digits, `. _ + -`, 40 at most). A tag of `""` is a cleared tag (its configuration's `tag` key does not give it again). The older one-line file (the tag) and the older empty file (a cleared tag) still read, as `tag = <line>` and `tag = ""`; the next write makes them TOML. `record.read_labels` reads the file, `record.run_tag` its tag (None when it has none), `record.run_labels` the other labels, `record.write_labels` and `record.write_run_tag` write it (a tag written keeps the labels).

`heimdall tag <A>/<E>/<R> [WORD …] [--clear]` shows or sets them: a bare word is the tag, `key=value` sets that label, `key=` removes it, `tag=` clears the tag alone, `--clear` removes all and leaves the tag cleared. The words are checked before anything is written. `heimdall run --tag` and a configuration's `tag` set the tag only; a Run's other labels stay. The plot document's `[source].tag` and `[source].labels` mirror the record's (`plotdoc.write_tag`); a tag or label is never in an identity.

**Across.** Each label key some Run of an errand has is an attribute `@<key>`, an axis beside `@tag`: a value for each distinct label, a Run without it having the value `unlabelled` labelled "–". It pages and curves like a quantity, and it is in what makes two points the same, so Runs that differ by a label never shadow each other. The record's labels are read when there is a record, else the document's `[source].labels` (a copied `results/`). A label named like one of the Runs' quantities is refused, naming the way out (`heimdall tag <Run> key=`, or another name). A label in `[from].ignore` is not supported: `ignore` takes quantities and `@events`.

**No longer holds:** the tag file being one line (`stable/internals/provenance.md`); a Run having one tag and nothing else to tell it by.

**Decisions:** the tag stays one file, and the tag is one label among the others; an old file is told apart by having no `=`. A Run without a label gets the value `unlabelled`, labelled "–". A label is in what makes two points the same, as the tag is. `[from].ignore` takes no `@<key>` (it never took `@tag`). `--tag` and a configuration's `tag` set the tag alone, so labels survive a rerun.

**Stable pages need:** `internals/provenance.md` (the tag file's TOML), `guide/plots-across.md` (`@<key>` axes), `guide/watching.md` (`heimdall tag`'s words).
