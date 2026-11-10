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

### Canonical cards' off-plan decisions (2026-11-10)
The implementer made these under the developer's word for the session ("make decisions by yourself… see this implementation run to end"). V274 and V275 are in [the live doc](../docs/live/canonical-cards.md).
- **Pythia's argv is `{card}`** (V274), a P3 miss found in P5: App_Pythia read its raw bases and the point card. The developer said yes to the fix and to rewriting the golden file (125 Pythia points, `argv[2]` alone).
- **Entries that became one physics** (V275): the most linked stays in the library; each other is its Run's own `<name>.adopted-duplicate` beside its link. In work dir 1, the 12 `_antikt` entries of `01_sherpa_pdf_dr_alg`.
- **256 entries of work dir 1 fail `heimdall library verify`:** no Run proves them, so their `identity.json` is still the old form. Each is linked only by points stale before the remake. A run of their Runs makes new entries, and `library prune` then removes the old ones.
- **Left for the developer to delete:** the remake's `.format1` copies in work dir 1, and the snapshot `~/heimdall-baselines/pre-remake-20261110/`.
- **`test_prune_removes_what_no_run_links_and_verify_reports_what_is_wrong`** now breaks an entry it names: it took the first its glob listed, which the new keys made the entry it also deletes.

- **A real study's config fails `heimdall check`.** Its `[plot].sets[4].curves[1].pdf` names a PDF that its `[quantities.pdf]` does not enable (seen 2026-11-08). It is the study's file, so Heimdall does not change it.

## Rounds

### Canonical cards, 2026-11-10: final configs and the identity that hashes them (I-149)
- **Source and plan:** I-149, planned as `canonical-cards` and gated on 2026-11-09; the plan, its logs and the one-off are in git at `7c1a205` (`.plans/plans/canonical-cards/`).
- **Built** (`d765cd5..ec53974`, local, not pushed): `runner/cards.py` (a card as entries, merged by priority and written in its folder's order); pythia, herwig and delphes read a final config, with a key twice in a free card refused; the rendered tools' final configs; the identity hashing each final config (no `base_sha256`, the library key the identity, record format 2, the prepare key); Pythia's argv `{card}`; work dir 1 remade by the one-off. Decisions V268–V275, in [the live doc](../docs/live/canonical-cards.md).
- **Suite at `ec53974`:** 2363 passed, 11 skipped, 2 xfailed, 0 failed (18 min).
- **The review:** not by another session. On the developer's order ("Just quick recheck and close it"), the implementing session rechecked: the code against the live doc (`argv` `{card}`, `FORMAT = 2`, `LAYOUT = 1`, no `{cards}` left), and work dir 1 against its snapshot (the drawable members the same before, after and now; `verify` the 256 unproven entries alone; the 24 set-aside folders there). Closed with that.

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
