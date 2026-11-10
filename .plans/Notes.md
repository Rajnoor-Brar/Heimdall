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

### The Grand Ranking's off-plan decisions (2026-11-11)
The implementer made these alone; the plan's own decisions were the developer's at two gates (2026-11-10, 2026-11-11). Each is stated in [live-grand-ranking-choices](../docs/live/grand-ranking-choices.md) as V287–V298; the full list, with step and why, is in git at the close's parent (`.plans/implementation/Implementation_Notes.md`).
- **`rank --json`** writes a missing number as null, `loss` wherever it said `score`, a vetoed point's rank null (V287).
- **A terminal that is not UTF-8** gets ASCII forms of every sign `rank` prints (V288).
- **`migrate`** rewrites `heimdall score` in a comment only, a section's `stats` under `[[report.section]]` only, and every form of `[score]` (V290).
- **Edge values:** `peak_bin_ratio` NaN with no yield; a `one` metric's thresholds on |log₁₀ m|; α = 0 trims nothing (V291).
- **A set without measured bins** has no leaderboard now that `chi2_ndf` is not a default (V292).
- **A figure weight's source** is `figure`, named by its page, not by the figure (V293): naming the figure needs `page_weights` to carry it, a shape change left to you.
- **Marginal headlines** and "indistinguishable" at ≤ 2 SE (V294); **the summary's front order and "Made by"** (V295); **the leaderboard's columns** and "Metric values" (V296).
- **`--head-to-head`** on `plot` and `report` kept in the sidecar with its source (V297).
- **`yield_sign`'s thresholds (0, 1)** (V298), and the integrity metrics compressed like any (the second gate).
- **`migrate` rewrites `configs/` only**, never a record, unlike earlier renames (V282): gate answer 1, narrowed.

- **A real study's config fails `heimdall check`.** Its `[plot].sets[4].curves[1].pdf` names a PDF that its `[quantities.pdf]` does not enable (seen 2026-11-08). It is the study's file, so Heimdall does not change it.

## Rounds

### Grand Ranking, 2026-11-10 to 11: gates, curated metrics, matched marginals, the record (I-151)
- **Source and plan:** I-151, the design plan `grand-ranking` (an audit of four real Runs, B1–B4), approved 2026-11-10; the implementation round's second gate at its milestone, 2026-11-11 (the veto optional; phase 7 into scratch; the close after a review). The plans, logs, ledger and probes are in git at the close's parent (`.plans/plans/grand-ranking/`, `.plans/implementation/`).
- **Built** (`4d225a3..` the close, local, not pushed):
  - the renames (`[score]` → `[ranking]`, `heimdall rank`, loss, category, metric ids, polarity), refused in a user's file, read in a record, rewritten by `migrate`;
  - opt-in integrity gates, and the integrity metrics scored by default;
  - compressed costs, eleven curated defaults, figure weights in the loss;
  - matched, trimmed marginals with a paired test;
  - the method record, rendered as "Made by" under every table, at the summary's front, in the report and in `rank` (`--method`, `--json`);
  - a test that no setting moves a number the record does not name;
  - the live docs `live-grand-ranking` (V276–V286) and `live-grand-ranking-choices` (V287–V298).
- **Benchmarks** (phase 7, read from the work dir, written to `~/Himinbjorg/forge/scratch/grand-ranking/`, the work dir's Runs unchanged):
  - **Defaults:** every pathological point ranks last by its loss, with none vetoed.
  - **Gates on:** 12, 6, 1 and 0 vetoed.
  - **Shares:** the largest category share is 31–42 %.
  - **Agreement:** B4 against 05's "today" has Spearman 0.961, and the engine matches the hand computation to 2e-15.
  - **Against each Run's old summary:** Spearman 0.894 (B1), 0.685 (B2), 0.853 (B3), 0.628 (B4). B4's old table had no measured bins.
  - **One item fails under the defaults:** B1's dr32 is not distinguishable (I-157).
- **Suites at the review** (`173ba4e`): fast 2315 passed, 11 skipped; full 2496 passed, 11 skipped, 2 xfailed, in 47 min. Each run's only failures were the two stable-docs reds (I-152). The developer's Sherpa jobs kept the load at 32–34 throughout. After the fixes: fast 2320 passed; `test_plot_stage` 53, `test_report_draw` 2.
- **The review** (stage 4, by an agent that did not implement, on the developer's choice): five proven defects, each fixed with a test that fails on the old code:
  - `rank --json` crashed on any NaN (high);
  - `rank` crashed on an ASCII terminal; its test faked the stream (medium);
  - the record said "no gate is applied" above `veto_loss`'s vetoes (low);
  - `migrate` missed three forms of `[score]` its refusal sends to it (low);
  - a test cited a plan id (low).

  One more item is for a decision (I-158). **Verdict:** sound after the fixes.

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
