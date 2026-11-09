# Notes

What the developer has still to read and is not a task. Rules: [work](../docs/rules/work.md) (the pipeline's stage 5). Tasks are in [Issues.md](Issues.md).

An entry leaves when the developer has read it: a decision accepted is already in `docs/stable/design/decisions/`, and one rejected becomes an issue.

## Waiting for the developer's yes

### Round 1's off-plan decisions (2026-11-09)
The implementer made these alone. Each is in the stable docs since round 1's crystallise (V235–V262).
- **Run state.** `runs.RunState` also carries `shown` and `ended`, where the plan named only `word`, `detail` and the qualifiers. `shown` is the verdict as written, so a free-text verdict prints unchanged, and `ended` lets the turn rule treat "a finished run in no set" as before.
- **`--state forgotten` matches the word.** A paused run that was forgotten stays `paused` (`paused, forgotten`). Only a queued run that left its queue has the word `forgotten`.
- **A requeued lost run is marked `resumed_by`**, as a resumed pause is. So it reads `lost, resumed`, a second `--resume-queue` finds nothing to do, and a waiter behind it follows it to the new run. A run counts as begun when its entry lists a record. The command stops at the first relaunch that fails.
- **Completion's directive line starts with a colon** (`:plain`, `:nospace`, `:files:<glob>`, `:dirs`), since a candidate could be named `dirs`.
- **Completion offers no live number `[N]`, only ids and pids.** The registry alone does not number runs as `heimdall runs` does: that also asks the sockets and Slurm.
- **`complete.py` never imports `cli`.** `cli.main` hands it the parser.
- **Commits.** Three pairs of steps went in one commit each (2.1 with 2.2, 1.2 with 1.3, 6.1 with 6.2), each with its reason in its phase log. The commit trailer names the model that did the work.

### About the developer's own files
- **A real study's config fails `heimdall check`.** Its `[plot].sets[4].curves[1].pdf` names a PDF that its `[quantities.pdf]` does not enable (seen 2026-11-08). It is the study's file, so Heimdall does not change it.

## Rounds

### Round 1, 2026-11-09: clean-up and core
- **Source and plan:** the code audit of 2026-11-08 and the plans of 2026-11-07, gated by the developer on 2026-11-09. The plan, its ledger and its logs are in git at `f8ee7eb` (`.plans/implementation/`). The sources are at `7bed373`.
- **Built** (`7bed373..f8ee7eb`, local, not pushed):
  - run state as a value (`runs.RunState`, `runs.STATES`), with registry entries parsed once (`runs.RunEntry`) and `runs.VERSION = 2`, where a newer entry is never acted on;
  - one point-state function, and the dead code taken out;
  - `log` and `show` sharing their options;
  - a pid's start time from `ps` where `/proc` is missing;
  - the points library as one module (`runner/library.py`);
  - `heimdall runs --resume-queue`;
  - TAB completion (`complete.py`, `env/complete.bash`);
  - the known reds named (strict xfails, a skip) and the `test_detach` flake fixed at its cause (an inherited ignored SIGHUP);
  - a crystallise of 25 live docs (V235–V262).
- **The review** (stage 4, 2026-11-09, by another session):
  - **Diffs read:** every code commit's, the riskiest first: run state, entries, requeue, completion, library.
  - **Suites, at `f8ee7eb`:** the fast suite gave 2131 passed, 11 skipped, 0 failed. The full suite gave 2311 passed, 11 skipped, 2 xfailed (I-79's two) and 1 failed, in 17 min, with a study's run and a watch on the machine too. The one failure was `docs/MAP.md`, left stale by the close's own edit of `work.md` and regenerated; `test_docs` then gave 551 passed.
  - **Proven defects:**
    - TAB completion goes silent after a word holding `=` or `:` (I-132);
    - `ISSUES.md` cited the wrong issues: I-97 named I-129 for set-merge's band, I-21 and I-75 were blocked on the done I-10 and I-11, and the order line listed the closed I-72 and I-73 (fixed in the close).
  - **Not proven:**
    - the requeue's real relaunch, since its test fakes `runs.relaunch`, and a sweep member's argv (`--sweep-member KEY --queued-to ID --detach`) never runs (added to I-07);
    - the crystallise's step 4 for pages the round did not touch (I-138).
  - **Nits:** in I-139.
  - **Verdict:** sound. The turn rule's behaviour is unchanged, which the patched-text test proves. The entry round trip is exact, and every reader of the registry reads `RunEntry` (`cluster.py` too). The library has no import cycle.
