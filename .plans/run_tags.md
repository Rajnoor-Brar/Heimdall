# A Run's tag, and axes ignored across Runs (I-113)

Asked by the user on 2026-10-31: "Have each Run have a tag, which is used to distinguish points when plot —across.
As well as ability to ignore variant of certain axes across runs in —across". The names here are I-112's: an
Assignment (today's project) holds Errands (today's run TOMLs, `results/<P>/<name>/`), and a Run is one numbered
execution of a configuration (`results/<P>/<name>/02_generator_pdf/`). Built after I-111 and the review of Copilot's
changes (I-114, V219–V222), before I-112 renames everything (its sweep then renames this too).

## 1. What is there (main after I-111)

- **Drawing an Errand's Runs together** (V169, `plotdoc.load_across`, 03 §3.3): `results/<P>/<name>/plot.toml` holds
  `[from]` (`runs`: folder globs; `prefer`: "last" or "all") and the config's `[plot]` with its `[plot.across]` sets.
  Its members are every Run's points, named `<run>__<point>`, their quantities matched by tag across the Runs, with
  the attributes `@events` (an axis), `@run` (the folder) and `@configuration` (named to be used).
- **Two Runs' same point** (every quantity's tag and the event count the same) is the later Run's with
  `prefer = "last"`, both with "all".
- **A Run's facts** are its plot document's `[source]` (rewritten by every run of the folder) and its record
  (`records/<P>/<name>/<NN_cfg>/`: `config/`, `logs/`, `points/`, `points.json`).

## 2. Decided (the user, 2026-10-31)

- **T1 Where a tag comes from:** `heimdall run … --tag NAME` gives every Run that invocation makes or resumes that
  tag; a configuration's `tag` key (inherited from the Errand's table, as other configuration keys are) is the
  default; `heimdall tag <A>/<E>/<R> [NAME]` shows or changes it afterwards (`--clear` removes it). A tag is a short
  name (letters, digits, `.`, `_`, `+`, `-`; at most 40). A Run keeps its tag: a resumed Run with no `--tag` keeps
  the one it has, and an untagged Run behaves exactly as now.
- **T2 Kept with the Run:** in its record (`records/…/<run>/tag`, one line, the source of truth) and in its plot
  document's `[source].tag` (written from the record each time the document is), so a copied `results/` keeps it.
- **T3 In `--across`:** a fourth attribute, `@tag` (each Run's tag; labels the tags themselves), an axis as
  `@events` is (a set that does not name it gets a page per tag, so two Runs' curves never share a label
  unseen); a point's identity across Runs includes its Run's tag, so Runs of different tags never shadow each other
  and re-runs under one tag do (the latest wins, as now). `heimdall runs` and a report's sources show the tag.
- **T4 Ignored axes:** `[from].ignore = ["generator"]` (and the config's way to write it, below): an ignored quantity
  is not an axis across Runs: it never splits pages or curves and never keeps two Runs' points apart. It must hold
  one value within each Run (else the drawing is refused, naming the Run and its values); the Runs are then told
  apart by their tags (or folders). Its label stays in the set's sub-header and a report's facts, per Run.
- **Writing `[from]` from the config:** the Errand's `[plot.across]` keeps sets; `runs`, `prefer` and `ignore` go in
  a new `[plot.across_from]` table beside it (checked as `[from]` is), copied into the document when it is written
  and by `--style-sync`.

## 3. Phases

| Phase | What | V-row |
|---|---|---|
| T1–T2 | `--tag`, the configuration key, the record and `[source].tag`, `heimdall tag`, `heimdall runs` showing it | V223 |
| T3–T4 | `@tag` across, identity with the tag, `[from].ignore` and `[plot.across_from]`; docs, tests | V224 |

## 4. Execution map

| Phase | V-row | Commit | State |
|---|---|---|---|
| T0 this plan, I-113 | — | | written |
| T1–T2 `--tag`, the `tag` key, the record and `[source].tag`, `heimdall tag`, runs, status, a report's sources | V223 | 4962bca | done |
| T3–T4 `@tag` across, the tag in the shadowing key, `[from].ignore`, `[plot.across_from]`; 03 §3.3, 04 §11.4 | V224 | (this commit) | done |

## 5. Log

- 2026-10-31: T1–T2 built (V223), the precedence `--tag` > the folder's record > the configuration's `tag` key,
  `[run].tag` inherited; `records/…/tag` the truth, `[source].tag` written from it; `heimdall tag`; runs, status,
  the run's title, `--plan` and a report's sources show it. `heimdall cluster` has no `--tag` (its jobs keep the
  folder's or take the key). Next: T3–T4 (V224).
- 2026-10-31: T3–T4 built (V224): `@tag` only when a run is tagged (an untagged one `""`, labelled `untagged`), an
  axis in each choice; the run's tag in the shadowing key; `[from].ignore` (quantities or `@events`; out of the choice
  and the key, kept in the values; one value a run, else refused); `[from]` checked as the schema's `across_from`;
  `[plot.across_from]` written into `[from]` by a run and by `--style-sync` (with no table a sync keeps `[from]`).
  Untagged drawings byte for byte as before.
