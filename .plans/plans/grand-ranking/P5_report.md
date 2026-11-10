# P5 · Leaderboard and sections

Verified when: the summary's sections are 04's, in its order; the leaderboard is flat when cells share objects and reference; per-metric detail is opt-in; head to head and detail have CLI flags; the report's default sections follow.

### 5.1 The summary model (M)
- Acceptance: `bars.summary_model` builds §1 Leaderboard (with Metric values), §2 Quantity marginals (with headlines), §3 Categories (one ranking each, the gates applied), §4 Baseline, §5 Head to head; polarity in every header and the legend in every table's first note; figure weights read (`bars.py:788`).
- Files: `framework/plot/figures/bars.py`, `framework/plot/figures/webpage.py`, `tests/runner/test_summary_layout.py`.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_summary_layout.py -q`
- Seam: the document model (sections and their tables), not the PDF.
- Blocked by: P4.

### 5.2 The report and the CLI (S)
- Acceptance: `report.HEADLINE` as 04; `heimdall rank` with `--head-to-head`, `--detail`, `--trim`; `plot --stats-only` and `report` accept `--head-to-head`; the terminal tables carry the glyphs, ASCII when stdout is not UTF-8.
- Files: `framework/runner/report.py`, `framework/runner/scorecmd.py`, `framework/runner/cli.py`, `tests/runner/test_report.py`, `tests/runner/test_report_build.py`, `tests/runner/test_score_cli.py`.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest -m "not slow" -q` then `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest integration/test_plot_stage.py -q` alone
- Seam: `test_report` and the CLI's output on the fixture work dir.
- Blocked by: 5.1.

## Log
