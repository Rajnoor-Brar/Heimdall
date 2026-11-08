---
id: live-set-merge
summary: a set's merge: a quantity's values become one curve per combination of the other axes, by pooling statistics or a mean, with an optional band
affects: plots
issue: I-125
---

**Now holds:** a set (`[plot.sets.<name>]`) may carry `merge`, an entry or a list of entries `{ <quantity> = <what>, how, label, tag, band, settings }`, beside `pages` and `curves`. `<what>` is a filter's value (`"all"`, a tag, a glob, a list). A quantity has one role in a set: pages, curves or merge.

`sweep.merge_groups` applies the entries in the order written. The members whose value of the entry's quantity it names become one `sweep.Group` for each combination of the other axes (and of what earlier entries merged), taking the place of the first member; a combination with one member stays that point, and members the entry does not name stay as they are. A group stands in a page cell where a point does: its `point` and `values` leave the merged quantity out, its `leaves` are the points it is made of, however deep. Its name is the other axes' tags then the merge tags (`entry.tag`, default `<quantity>_merged`); its label `entry.label`, default `<quantity>, merged`. A merged quantity does not page the set.

Plan-time refusals (`sweep._merge_shape`, `sweep.check_set`): not one quantity in an entry, an unknown `how` (naming `combine` and the means), a `band` other than false, `"minmax"`, `"std"`, a quantity not swept or fixed, combined away by the configuration, or in two roles, a tag that is one of the quantity's own, and two entries of one quantity with the same tag. `heimdall plot … --plan` lists each merged curve with the points it is made of and `how`.

**Drawing.** `plot.merged_curves` (called by `plot.pages` before the pages' ROOT file is made) writes each group's file under the Run's working folder, `plots/<E>/<R>/sets/<name>.yoda`, rebuilt only when a member's YODA, `how`, its settings or the band changed (a stamp of their sha256). A group of groups merges the inner files first. The group is drawn by a stand-in member (the first point's, with the group's `point`, `values` and label), so a page, its look and its statistics treat it as a point. `how = "combine"` is `tools.merge_files` (rivet-merge, pooling the statistics); any other `how` is a mean of `stats.means.REGISTRY` taken bin by bin (the numbers in `stats/merge.py`, the YODA files read and written by `plot/figures/curves.py`, loaded as `derive.py` is): a scalar mean on each bin's values, an ensemble mean (`wasserstein`, `scale_aligned`) on the members' densities. `settings = { … }` are the mean's own (`floor`, `alpha`, …), refused if it takes none of them. The curves merged are the 1D estimates every member has (not `/RAW`, `/TMP`, the counters); a binning that differs is refused naming the object and the first edge; errors are written symmetric.

`band = "minmax"` draws the members' lowest and highest value in each bin; `"std"` the mean ±1 sample standard deviation (3 members at least, refused below). Both are written as two more files (`<name>__lo`, `<name>__hi`) whose objects are the curve's band members for Paint. A page that normalises (`[plot].normalise = "area"`) renormalises the merged curve as it does any; a cross-section page never does.

**Statistics.** A merged curve is a curve of its own: its row in `statistics.csv` has `point = <name>` (as the group is named), and `statistics.json` gets `merged`, `{name: [the points it is made of]}`. It has no axes, so a marginal never takes it and a baseline lists it as not a point of the sweep. It is scored as any curve: a mean curve can beat every member.

**No longer holds:** a set having only the roles `pages` and `curves`; a mean of curves existing nowhere (only `combine`, the `merged` figure and `band`'s envelope).

**Decisions:** an entry has a `settings` table, because a mean of histograms with empty bins needs its `floor` and a mean's keys must not mix with the quantity's name. The merged file is not renormalised: `[plot].normalise` already does that at draw time. Errors are written symmetric, and only the 1D estimates every member has are merged. `band = "std"` needs 3 members. Band edges are two files, because Paint's band is an envelope of band members. A merge of merges weighs each inner curve equally. The YODA reading and writing is `plot/figures/curves.py`, not `stats/merge.py`, because the stats package may not import YODA. A merged curve's members are in `statistics.json` (`merged`), not a csv column, because a new column is a format change every reader meets.

**Stable pages need:** `guide/plots-sets.md` (the merge role, `how`, `band`, `settings`), `guide/plots-statistics.md` (merged rows, `merged` in the sidecar).
