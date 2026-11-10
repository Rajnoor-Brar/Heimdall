"""framework/stats/ — measuring, ranking and comparing curves.

One seam: Paint measures (the bins it compared, `measured` in a page's stats.json), this package computes (metrics,
means, losses, the ranking), and the plot and report code only presents. It uses numpy, the standard library and
`runner.errors`; it never draws, and the runner imports it only inside functions (tests/runner/test_imports.py).

* bins     — a page's measured bins as arrays per curve
* metrics  — REGISTRY of named metrics, each with a category, a polarity, a scale, thresholds and a note; ALIASES of old ids
* means    — REGISTRY of means (the power mean family) with their error rules
* merge    — the numbers of a set-merge, bin by bin: K members into one curve
* table    — the statistics table: its rows from Paint's numbers, its csv, and its sidecar statistics.json
* ranking  — the engine: rows in, each point's loss and its place out, with the marginals and the baseline
"""
