# Implementation issues, round 1

Written by the implementing agent. Findings left open, appended as found. Each is a claim with where it was seen: what failed or is wrong, the output or the line, and what it blocks (a step id, or nothing). Each one gets an `I-` id at P8.1, or is marked closed here with why.

## Open

- **2026-11-09, P7.1: tests that list live runs see the machine's own.** `test_detached_runs.py::test_jobs_changes_…` failed in the full suite: a run of the user's, live on this machine, was `[1]` in the test's `heimdall runs` listing (found by its watch socket, which no test directory scopes), and the test expected the listing's words from before 2026-11-08 (`1 of 1 at once`). Fixed in the test (it finds its block by its pid). `test_cluster.py:298` and the file's first listing still read the whole listing. Blocks nothing. → I-129.
- **2026-11-09, P3/P4 (the library): `library = "only"` keeps the Run's `logs/` and `run.jsonl`, and `adopt` has not touched a real work dir.** The plan said "no folder" for `"only"`; the developer is to confirm. `adopt` waits for the long runs to end and the developer's yes. Blocks nothing. → I-130.
- **2026-11-09, P5: TAB completion tested by a driver, not by hand.** Not tried in a terminal on a real work dir, nor under a cluster login node's bash (`compopt`). Blocks nothing. → I-131.

