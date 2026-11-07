---
id: live-set-merge
summary: a set's merge: a quantity's values become one curve per combination of the other axes, by pooling statistics or a mean, with an optional band
affects: plots
issue: I-125
---

**Now holds:** a set (`[plot.sets.<name>]`) may carry `merge`, an entry or a list of entries `{ <quantity> = <what>, how, label, tag, band }`, beside `pages` and `curves`. `<what>` is a filter's value (`"all"`, a tag, a glob, a list). A quantity has one role in a set: pages, curves or merge.

`sweep.merge_groups` applies the entries in the order written. The members whose value of the entry's quantity it names become one `sweep.Group` for each combination of the other axes (and of what earlier entries merged), taking the place of the first member; a combination with one member stays that point, and members the entry does not name stay as they are. A group stands in a page cell where a point does: its `point` and `values` leave the merged quantity out, its `leaves` are the points it is made of, however deep. Its name is the other axes' tags then the merge tags (`entry.tag`, default `<quantity>_merged`); its label `entry.label`, default `<quantity>, merged`. A merged quantity does not page the set.

Plan-time refusals (`sweep._merge_shape`, `sweep.check_set`): not one quantity in an entry, an unknown `how` (naming `combine` and the means), a `band` other than false, `"minmax"`, `"std"`, a quantity not swept or fixed, combined away by the configuration, or in two roles, a tag that is one of the quantity's own, and two entries of one quantity with the same tag. `heimdall plot … --plan` lists each merged curve with the points it is made of and `how`.
