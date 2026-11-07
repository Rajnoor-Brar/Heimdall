---
id: live-across-axes
summary: Runs with different axes drawn together: every member has every quantity (a quantity a Run never names is unset there), Runs told apart by serial, heimdall diff, Run labels as axes
affects: plots
issue: I-126
---

**Now holds:** `plotdoc.load_across` gives every member a value for every quantity of the across set. A member's `values` already hold its Run's fixed quantities (a plot document writes the point's static values with its choice), so a pdf sweep at a fixed event count and an event-count sweep at a fixed pdf meet on a pdf × `@events` page, and the point they both have is the later Run's (`prefer = "last"`) or both (`"all"`).

A quantity some Run never names (not in its members' values) gets one more value, tagged `unset` and labelled "not set" (`plotdoc.UNSET`; `unset_` if a value already has that tag), and that Run's members take it. They page apart from the Runs that did name it and are never taken for the same points as theirs: the Run may set it some other way, and across does not guess. `[from].ignore` still removes a quantity everywhere.

**Runs named where they meet.** `plotdoc.run_label(folder, tag)` names a Run `NN·<its tag, else its folder's label>` (`03·nlo`), its serial the folder's leading digits (a folder with none is named by its tag or folder alone). The across `@run` quantity's labels are these; a member's `context["run"]` is its Run's; and a curve labelled by the `@tag` axis reads `NN·<tag>` (`plot._curve_label`), so two Runs of one tag that `prefer = "all"` keeps are told apart, and a Run added later changes no label. A table of Runs together (`statistics/<set>/statistics.csv` with Run members) has a `run` column after `point`, listed in `statistics.json`'s `columns`; a table with no Runs together has none (`stats.table.columns_for(names, run)`).

**`heimdall diff <A>/<E>/<R1> <R2>`** compares two Runs of one Errand from their records, read-only. `<R2>` may be the folder alone (beside the first). It prints what differs in the errand file each ran with (key by key, `old → new`), the configuration and `--set`s, any other snapshot file (a card) by hash with its changed lines (the first 12; `--full` for all), and for each point both have, its identity parts tool by tool (`exe_sha256`, options, card). Equal points are counted, not listed; points only one Run has are named. `--points` keeps names or globs, `--json` prints the same as data. Heimdall's revision is not a difference. Two Runs of different Errands, or of one Run with itself, are refused (`runner/diffcmd.py`).
