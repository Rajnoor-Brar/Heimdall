# A report's context first: what was run, how the numbers are made (I-111)

Asked by the user on 2026-10-27, after I-110's report: "Place tools config and notes on quantity formula and meaning
(make proper para per quantity) earlier to give context as to what was run and so, then and emergent results and
plots and stats etc".

Read as: a report opens with what was run (the tools' configuration) and with what each statistic is (its formula and
its meaning, a paragraph each, now numbered footnotes repeated at the end of every statistics part), and only then
shows its results (pages, statistics, bar tables). "Quantity" here is a statistic (χ²/ndf, |Δ| / reference, …): the
notes it names are the ones that give a formula and a meaning (`bars.NOTES`).

Built in the worktree `scratchpad/heimdall-context`, branch `context` (from main at `06bc3b7`); main fast-forwarded at
the end. **Pause at the end:** the Brookhaven report's PDF sent.

## 1. What is there (main at `06bc3b7`)

- **Order:** a report's sections are its recipe's, in its order; the default report ends with Tools (V210).
- **The definitions:** `bars.NOTES[<statistic>]` (formula, then what it sums over and what it means) is note
  `stat-<statistic>` of every item that shows the statistic; `COMPARED` (`compared`), `SCORE_NOTE` (`score`), `H2H_NOTE`
  (`h2h`), `APART` (`apart`) and the data-only rule (`counted`) are the method's notes. Every statistics part typesets
  its own notes, numbered, at its end (`typeset.document`): the same definitions again in each part, as small print.
- **Bar tables** (`typeset.bars`) show the six statistics with no definition at all.

## 2. Decided

- **C1 Context first:** the tools sections come first, in the recipe's order, then *How the numbers are made*, then
  every other section in the recipe's order (`resolve` orders them, so `--list`, the folders' numbers and the
  contents agree). `[report].context = "last"` puts both after the results, as an appendix. The default report's
  sections are written so (Tools first); `--init`'s starter too.
- **C2 How the numbers are made** (`[report].method`, default true): an unnumbered section, in the contents, whenever
  the report shows statistics or bar tables:
  - *The statistics:* a paragraph each for those the report shows, in the summary's order: its name, its formula
    typeset as display math (`bars.FORMULAS`, LaTeX), then what it sums over and what it means
    (`bars.DEFINITIONS`, from which `NOTES` is now composed, byte for byte as before);
  - *How a page is compared* (`COMPARED`);
  - *How points are scored* (`SCORE_TEXT`, `APART`, and each part's data-only rule), and *Head to head* (`H2H_TEXT`),
    when a part shows the standings.
  The statistics parts then leave those notes out (their marks too) and keep the ones on reading their own tables; a
  part's tagline links the section. Each part's HTML page keeps every note (it stands alone).
- **C3 Brookhaven's `zeus_report.toml`:** Tools moved first in the file, `context` and `method` written out.

## 3. Phases

| Phase | What | V-row |
|---|---|---|
| C1–C3 | the order, the method section, the parts' notes, the schema keys; tests; docs; Brookhaven's recipe built read-only; the suites; main fast-forwarded | V218 |

## 4. Execution map

| Phase | V-row | Commit | State |
|---|---|---|---|
| C0 this plan, I-111 | — | | written |

## 5. Log
