---
id: plots-across
summary: the Runs of an errand on one page: [plot.across], @events, @tag, [from], prefer and ignore
code: framework/runner/plotdoc.py, framework/runner/plot.py
---

# The Runs together

Sets put one Run's points on pages. To put several Runs' points on one page (the same points at 10k, 100k and 10M events, or two configurations side by side), declare sets across them:

```toml
[plot.across.events_by_pdf]
pages  = { generator = "all", pdf = ["NNPDF23lo", "MSTW08lo90cl"] }
curves = { "@events" = "all" }       # a curve per Run's event count

[plot.across_from]
runs   = ["0[3-9]_*"]
ignore = ["generator"]               # the Runs' tags tell them apart

[plot.across.by_tag]
pages  = { pdf = "all" }
curves = { "@tag" = "all" }
```

**Members** are every Run's points, named `<R>__<point>`, with quantities matched by tag across Runs, plus attributes:

- `@events`: the Run's event count (tags like `10M`). An axis: a set not naming it gets a page per count.
- `@tag`: the Run's tag, there only when a Run is tagged; an untagged one is labelled `untagged`. An axis as `@events` is, so two tags' curves never share a page unseen.
- `@<key>`: each label key some Run has (`heimdall tag <Run> shower=new`) is an axis beside `@tag`, a value for each distinct label and `unlabelled` ("–") for a Run without it. It pages and curves like a quantity, and tells points apart, so Runs that differ by a label never shadow each other. A label named like one of the Runs' quantities is refused, with the way out; `ignore` takes quantities and `@events`, no `@<key>`. The labels are read from the records, else from the document's `[source].labels`.
- `@run`, `@configuration`: its folder and configuration. Not paged by themselves.

**Runs with different axes meet.** Every member has a value for every quantity of the set: a quantity a Run never names gets one more value, tagged `unset` and labelled "not set", and that Run's members take it. They page apart from the Runs that named it, and are never taken for those Runs' points: across does not guess. So a pdf sweep at a fixed event count and an event-count sweep at a fixed pdf meet on a pdf × `@events` page, and a point both have is the later Run's (`prefer = "last"`) or both (`"all"`).

**Runs are told apart by serial.** A Run is named `NN·<its tag, else its folder's label>` (`03·nlo`) wherever Runs meet: the `@run` labels, a member's `run` context, and a curve labelled by `@tag`. So two Runs of one tag that `prefer = "all"` keeps never share a label, and a Run added later changes none. To see what two Runs did differently: [`heimdall diff`](housekeeping.md).

**`[from]`**, in the document, from `[plot.across_from]`:

- `runs` names Runs by folder globs; every Run by default.
- `prefer = "last"` draws a point two Runs have from the later, and says so; `"all"` keeps both. Runs of different tags never stand for each other.
- `ignore` names quantities (or `"@events"`) that are no axis across Runs: never paging, never telling curves apart. Each must hold one value within each Run, or the drawing is refused.

**Where:** `results/<A>/<E>/plot.toml`, written by a job when it has none. Pages go to `results/<A>/<E>/plots/<set>/`. Drawn by `heimdall plot <config> --across`, measured by `heimdall plot <config> --across --stats-only`. `--style-sync <config> --across` takes the config's `[plot]`, `[plot.across]` and `[plot.across_from]`.
