"""framework/stats/ — measuring, scoring and comparing curves.

One seam: Paint measures (the bins it compared, `measured` in a page's stats.json), this package computes (metrics,
means, scores), and the plot and report code only presents. It uses numpy, the standard library and
`runner.errors`; it never draws, and the runner imports it only inside functions (tests/runner/test_imports.py).

* bins     — a page's measured bins as arrays per curve
* metrics  — REGISTRY of named metrics, each with a purpose, a direction, thresholds and a note
* means    — REGISTRY of means (the power mean family) with their error rules
"""
