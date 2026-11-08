# Implementation issues

Findings from implementing the plans, left open: each is a claim with where it was seen. Not in [ISSUES.md](ISSUES.md) yet; the developer decides which move there. Entries are appended as found.

## From stats-backend (2026-11-07)

### F-2 A figure's `weight` is not read by the summary
`[figure].weight` is accepted and checked, but `bars.py` has no figure for a page, so only `[score].weights` globs weigh pages. **Done when:** a page's figure weight reaches the score, or the key is refused.

### F-4 Fixture identities of the Herwig, MadGraph and Sherpa tools hash an absolute cache path
So a moved cache or another checkout changes every identity there. Ask-first territory (identity). **Done when:** the path is not in the hash, by the developer's order.

### F-6 `test_the_rank_table_is_the_runners` fails
`docs/stable/internals/runner.md`'s rank table lacks `| 4 | \`scorecmd.py\` | heimdall score: the standings, marginals and baselines read from a statistics.csv, a row a Run for an errand |`. Likewise `diffcmd.py` (rank 5): `heimdall diff`, what two Runs of one Errand did differently. A stable page: edit on the developer's order.

### F-7 Stable pages to crystallise
`docs/stable/guide/plots-statistics.md` and `docs/stable/guide/reports.md` still describe the five old columns, `top5` and `scoreboard`. Crystallise from [scoring](../docs/live/scoring.md) on the developer's order.

### F-9 Known failing tests, not from this work
`test_detach::test_the_first_signal_stops_cleanly_the_second_hard`, `test_docs::test_the_code_a_page_names_exists[stable/internals/plot-backends.md]`, `test_stack_build::test_the_old_way_is_apt_and_a_venv`; the slow `test_gates_p1` byte-for-byte references differ at a digit.

### F-11 The cells-against-curves table is kept, the `area` table and panel dropped
`<metric>:crossed` stays though the plan named only `ranking|table`; the `area` column stays in `statistics.csv`. Say if either should go.

### F-12 A real study's config fails `heimdall check`
`[plot].sets[4].curves[1].pdf` names `NNPDF23nlo`, which the file's `[quantities.pdf]` (two points enabled, the rest commented out) does not have. Seen 2026-11-08 while building the baseline errand, which imports it. A study's own file: not changed.
