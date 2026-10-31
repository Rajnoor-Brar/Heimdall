# Copilot's changes reviewed, and their fixes (I-114)

Asked by the user on 2026-10-31: "read .plans/Copilot_Changes.md and check the quality of implementation". Copilot's
work (2026-10-28 to 30, four changes, found uncommitted on main) is commit `c45b6d0` (branch `copilot`); the fixes
are built on branch `context`, above it and I-111. A review of four read-only agents (ranges, overflow marks, runs,
watch) gave 33 findings, 8 major; the majors were checked against the code by hand (M1–M4 confirmed so far).

## 1. Findings and what is decided

**Axis ranges (`[plot].x_range`, `y_range`)**
- **R1 (major, confirmed)** Paint's new checks (main.cc ~163–169) run on ranges Paint calculated itself: an empty
  log-y page (y.lo = 0), all-zero MC on log y, log x from a 0 edge now fail with an error naming x_range/y_range and
  lose their statistics. *Fix:* check an axis only when it has an explicit endpoint; tests for those pages.
- **R2 (major, confirmed)** `[plot]`-level ranges reach statistic-figure pages (plot.py ~1031). *Fix:* the statistic
  figure's table resets both to `["default","default"]` unless the figure sets them; a test.
- **R3** Heat maps: `[plot].y_range` lands on the 2-D y coordinate; bounds snap to bins; a range outside the histogram
  is ignored; a bad range exits 5. *Decided:* a heat map takes x_range/y_range only from its own figure; refused
  before drawing (Kit::Config, exit 1) when it misses the histogram; the bin snapping documented (03, 06).
- **R4** A `"default"` endpoint means "calculated", against V131's one meaning (the layer below). *Decided:* each
  endpoint resolved against the layer below in `page_settings` (a figure's `["default", 10]` keeps `[plot]`'s lower
  endpoint); at the bottom layer "default" is the calculated range.
- **R5** x_range quietly narrows the statistics (χ², areas). *Decided:* the ranges are display only: statistics are
  computed on the span before x_range/y_range; said in the notes and 03.
- **R6** nan/inf endpoints pass the schema. *Fix:* `check_value` refuses non-finite numbers in `length`/`ordered`
  lists, the ordered test written `not a < b`.
- **R7** `item_choices` crashes the editor-schema build on a list of strings. *Fix:* `{"enum": item_choices}` alone.
- **R8** 03 §3's example `y_range = [0, "default"]` fails every log-y page. *Fix:* `["default", 1e4]`.
- **R9** Tests: the YODA handoff test covers untouched code; Paint's refusals and heat maps untested. *Fix:* Paint
  `--ranges` output fed to the handoff; exit-code tests for the refusals; heat-map cases.

**Overflow marks**
- **O1 (major, confirmed)** With a ratio pad and `ratio.gap = 0` the lower marks sit under the ratio frame (Paint and
  mpl). *Decided:* when the ratio pad joins the frame (gap smaller than the mark's offset and width), lower marks are
  drawn just inside the main frame's bottom edge; documented; tests with `ratio = true`.
- **O2** Empty bins get underflow marks on log y. *Fix:* values ≤ 0 on a log axis are not marked.
- **O3** Off-scale reference data get no mark. *Decided:* documented: only MC curves are marked.
- **O4** Curves of different binnings overlap their marks. *Decided:* documented: the split is per shared bin.
- **O5** Tests miss ratio, log, x-span clipping and the sort order. *Fix:* cases for each.

**`heimdall runs`: listing and progress**
- **U1 (major, confirmed)** Pre, post and combined stage points count as completed but not in the total (7/3).
  *Fix:* pre/post points carry `stage` as combined ones do; the Recorder counts configuration points only.
- **U2 (major, confirmed)** A sequential sweep (`--stages`, `--only`) keys every configuration as `''`. *Fix:* the
  sequential loop wraps the bus in `RunBus` as `_pipelined` does; a test of two configurations sharing point names.
- **U3** The total grows only as each run starts. *Fix:* the planned total handed to the Recorder up front.
- **U4** The registry is rewritten on every point event inside the Bus lock (06 says begin and end). *Decided:* the
  entry kept in memory, written at most every 2 s and at each run's start and end; 06 says so.
- **U5** The serial column prints `00` for an unknown serial. *Fix:* `NN ` only when known.
- **U6** A reused pid read as "in another PID namespace" keeps a dead run listed as running. *Fix:* on
  PermissionError compare the process's start time with the entry's.
- **U7** `--1` abbreviates to `--10`; the help says `--N`. *Fix:* `allow_abbrev=False`; the help names the four.
- **U8** 05 and 06 do not describe the progress line, NULL or "lost". *Fix:* both.

**`heimdall watch` keys**
- **W1 (major)** `q` stops the run unconfirmed; F2's `ESC O Q` and typing `squeue` stop it too. *Decided:* `q`
  stays the stop (the user's ask); escape sequences are skipped whole in `follow`, so function and arrow keys never
  act as letters.
- **W2 (major)** A second `q` escalates to a hard stop, then a kill, unlabelled. *Decided:* after the first stop
  further `q`s are ignored, with a line naming the hard stop's command.
- **W3** 06 §10 and I-07's checklist still name `s`, `y`. *Fix:* both, and Copilot_Changes.md's claim corrected.
- **W4** Tests: a real SIGINT, `sy` then `d`, `qq`, an F2 sequence.

**All four** have no V-row: V219 axis ranges, V220 overflow marks (and YODA labelled deprecated), V221 the runs
listing and progress, V222 the watch keys (superseding V183's key clause), each written with its fixes.

**Brookhaven** (the user's; reported, not edited): d05's lower limit 1e-3 hides the ZEUS point at 7.5e-4; d04's
0.01 cuts an error bar; d01/d09/d10's upper 1e5 is two decades loose; the result documents disagree with each other.

## 2. Execution map

| Step | What | Commit | State |
|---|---|---|---|
| F0 | this record, I-114 | | written |
| F1 | ranges and overflow fixed, Paint rebuilt (scratch apps) | | |
| F2 | runs and watch fixed | | |
| F3 | V219–V222, fast and slow suites | | |

## 3. Log
