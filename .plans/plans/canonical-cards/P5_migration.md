# P5 The one-off: a work dir's records remade in the new form

The runner reads only the new form (gate Q4). This phase's script lives in `oneoff/` of this plan folder, never in `framework/`, and is deleted at the close with the plan.

**Verified when:** a fixture work dir recorded under the old form plans with nothing to run after the one-off, and its `status` and drawable points are the same as before. The old-form work dir is made by running the fixture at the commit before P4 in a scratch worktree, on the scratch roots. Then ⏸, on the developer's yes, work dir 1: a hard-link snapshot, a dry run, the remake, the comparison.

### 5.1 The proof that a record is its snapshot (S)
- Acceptance: `oneoff/old_identities.py`, run with the pre-P4 checkout on `sys.path`, writes `{run, point, old identity planned from the snapshot, marker}` for every complete point. A mismatch is listed, and that point is left untouched.
- Check: on the old-form fixture work dir, every point matches.
- Files: `oneoff/keys.py` (new; it prints old or new keys by the checkout it runs with, so it is 5.1's script and 5.2's input).
- Blocked by: P4.

### 5.2 The remake (M)
- Acceptance: `oneoff/remake.py`, with the new code, plans each Run's snapshot and writes the new `.complete` and `identity.json` (each after a `.bak`) for each proven point. It re-keys the library: renames each entry, relinks the Runs, and rewrites the index, `points.json` and each plot document (`plotdoc.rekey`). Dry run by default; `--yes` writes. It refuses while a job of the work dir goes. Provenance and seeds are untouched.
- Check: on the fixture: `status` and drawable points the same; `heimdall library verify` clean; `heimdall run … --plan` with nothing to run.
- Files: `oneoff/remake.py` (new); `oneoff/oldform.py` (new: the old-form fixture work dir, built with the checkout before P4).
- Blocked by: 5.1.

### 5.3 Work dir 1 ⏸ (S)
- Acceptance: on the developer's yes: a hard-link snapshot, 5.1's proof (its list of unproven points read), the dry run, the remake, then `status`, the drawable points and `verify` compared with the snapshot. Work dir 2 the same, if its records hold points.
- **Update work dir 2** (the developer, 2026-11-09: a task for later, on order, not now): back up its copy of the Decay card and delete its `HeavyIon:SigFitNGen = 0` line, as in the Decay fixture (answer A). It has no records, so nothing is remade.
- Check: the comparison files are equal; `verify` is clean.
- Blocked by: 5.2, and the developer's yes.

## Log

- 2026-11-10, 5.1: `keys.py` plans every Run from its snapshot (CONFIGS at the snapshot, the serial from the folder). Work dir 1, read-only: 1563 points; 840 proven (all old-state complete), 319 not (all stale), 404 not linked. 630 proven old keys → 618 new: 12 merges, each a `01_sherpa_pdf_dr` point (anti-kT from the base) and its `_antikt` twin in `01_sherpa_pdf_dr_alg` (anti-kT as a quantity), 1M events each, other seeds. Their final configs are equal; the old keys differed by the card header naming the point and the prepare dir that followed from it.
- 2026-11-10: the developer's choice for the 12: the most linked stays in the library, the other stays its Run's own beside its link, unlinked entries go. `library/.superseded/` was dropped: `prune --yes` would take it for an unlinked entry.
- 2026-11-10, a P3 miss found here: Pythia's argv was `{cards}`, its raw bases then the point card, so it never read the final config, and the base's path was in every Pythia identity (763 points of work dir 1; in the fixture, a base renamed was new physics). Fixed to `{card}` on the developer's yes, with `test_pythia_reads_the_final_config_so_a_renamed_base_is_the_same_identity`; the golden file rewritten again. Work dir 1 gains no merge from it (1187 keys either way).
- 2026-11-10, 5.2 checked on the old-form fixture (`oldform.py`, run with the checkout at 1a678e4 on scratch roots): lib_a and lib_c pool Demo/jets' pdf points, lib_c's base lib_a's with a comment more; one lib_a entry left with a wrong `.complete`. Old code: lib_a 3 complete 1 stale, lib_c 4 complete, verify 1 problem (the planted one). Remake: 7 proven, 4 rekeyed, 3 set aside. New code after: the same status, verify the same 1 problem in 5 entries, every plot member drawable but the planted one (as before), `prune --duplicates` keeps the 3 (other seeds), `library list` folds each entry with both Runs.
- 2026-11-10, 5.3, work dir 1 (the developer: "see this implementation run to end"): a hard-link snapshot in the baselines folder `pre-remake-20261110/`, with the old code's states, drawable members and verify, the keys, the dry run and the remake's output. Keys recomputed after the Pythia fix. Remake: 630 entries proven, 618 rekeyed, 12 set aside (each `01_sherpa_pdf_dr_alg` `_antikt` entry, beside its link), 24 Runs rekeyed, nothing unlinked to prune. After, by the new code: every point's state as before (840 complete, 319 stale, 340 to run, 44 incomplete, 12 stopped, 8 failed; none changed); the same 1160 plot members drawable; `verify`: 874 entries, 256 problems, exactly the entries no Run proves (one under `legacy`), whose identity.json is the old form. Each is linked only by points stale before; a run of their Run makes a new entry, and prune then removes the old. `prune --duplicates` keeps the 12 (other seeds).
- Work dir 2 has no records: nothing remade. Its update stays a later task (I-150).
