---
id: live-plot-doc-tags
summary: a plot document's members name their values by tag, so a quantity's points may be reordered or taken out of plot.toml; a member whose value is gone is left out of the drawing
affects: plots
---

**Now holds:** in `results/<A>/<E>/<R>/plot.toml`, a member's `choice` and `values` (`[members.<point>]`) and `[axes].fixed` name each value by its tag (`pdf = "MSTW08lo"`), not by its place in `[quantities.<q>].points`. Every writer goes through `plotdoc.dumps`, which writes them so (`plotdoc.by_tag`); `plotdoc.load` maps each tag to its place in the list as it is now. So the points of `[quantities.<q>]` may be reordered and every member keeps its value and label.

A point taken out of `[quantities.<q>]` (commented out, removed) leaves the members with that value out of the drawing and the statistics: `Doc.left` names each with the reason, and `heimdall plot` (and `--stats-only`) says so once (`plot.say_left`: `plot: N member(s) left out, a value not in the document's [quantities]: …`). The other members are drawn as before. For the Runs together (`--across`), each Run's left-out members are named `<R>__<point>`. The next run of the folder rewrites `[quantities]` and `[members]`, so a point taken out by hand comes back then; to leave a value out of every drawing, a set's filter or `heimdall plot RUN --points SEL` is the way.

A document written before (values as places, `pdf = 2`) reads as before; a place past its quantity's list is refused naming the member, not a traceback, and `heimdall migrate --plot-docs --apply` rewrites such a document by tag (`plotdoc.needs_upgrade` knows it). `statstable`'s axes read either form.

**No longer holds:** a member's value being an index into `[quantities.<q>].points`, so that taking a point out gave an `IndexError` in `sweep.label_of`, or moved every later member to another value's label; `[axes].fixed` as `#N`.

**Decisions:** a point's place in the errand file never mattered to a run: its identity and seed follow its content and its name its tags, so only the plot document needed this. In memory a member still holds indices (every page code reads them); only the file names tags. A value gone from `[quantities]` leaves its members out rather than refusing the document, because taking a point out is how one hides a value from that Run's drawing; the note says so each time. The record format is unchanged (`source.format` stays 1), as `record.FORMAT` is one number for every record file: an older Heimdall cannot read a document by tag, and nothing refuses it by format.

**Stable pages need:** `guide/plots.md` (The plot document: members by tag, a point taken out of `[quantities]` leaves its members out).
