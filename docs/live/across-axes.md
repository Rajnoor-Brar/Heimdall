---
id: live-across-axes
summary: Runs with different axes drawn together: every member has every quantity (a quantity a Run never names is unset there), Runs told apart by serial, heimdall diff, Run labels as axes
affects: plots
issue: I-126
---

**Now holds:** `plotdoc.load_across` gives every member a value for every quantity of the across set. A member's `values` already hold its Run's fixed quantities (a plot document writes the point's static values with its choice), so a pdf sweep at a fixed event count and an event-count sweep at a fixed pdf meet on a pdf × `@events` page, and the point they both have is the later Run's (`prefer = "last"`) or both (`"all"`).

A quantity some Run never names (not in its members' values) gets one more value, tagged `unset` and labelled "not set" (`plotdoc.UNSET`; `unset_` if a value already has that tag), and that Run's members take it. They page apart from the Runs that did name it and are never taken for the same points as theirs: the Run may set it some other way, and across does not guess. `[from].ignore` still removes a quantity everywhere.
