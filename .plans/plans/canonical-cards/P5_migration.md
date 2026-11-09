# P5 The one-off: a work dir's records remade in the new form

The runner reads only the new form (gate Q4). This phase's script lives in `oneoff/` of this plan folder, never in `framework/`, and is deleted at the close with the plan.

**Verified when:** a fixture work dir recorded under the old form plans with nothing to run after the one-off, and its `status` and drawable points are the same as before. The old-form work dir is made by running the fixture at the commit before P4 in a scratch worktree, on the scratch roots. Then ⏸, on the developer's yes, work dir 1: a hard-link snapshot, a dry run, the remake, the comparison.

### 5.1 The proof that a record is its snapshot (S)
- Acceptance: `oneoff/old_identities.py`, run with the pre-P4 checkout on `sys.path`, writes `{run, point, old identity planned from the snapshot, marker}` for every complete point. A mismatch is listed, and that point is left untouched.
- Check: on the old-form fixture work dir, every point matches.
- Files: `oneoff/old_identities.py` (new).
- Blocked by: P4.

### 5.2 The remake (M)
- Acceptance: `oneoff/remake.py`, with the new code, plans each Run's snapshot and writes the new `.complete` and `identity.json` (each after a `.bak`) for each proven point. It re-keys the library: renames each entry, relinks the Runs, and rewrites the index, `points.json` and each plot document (`plotdoc.rekey`). Dry run by default; `--yes` writes. It refuses while a job of the work dir goes. Provenance and seeds are untouched.
- Check: on the fixture: `status` and drawable points the same; `heimdall library verify` clean; `heimdall run … --plan` with nothing to run.
- Files: `oneoff/remake.py` (new).
- Blocked by: 5.1.

### 5.3 Work dir 1 ⏸ (S)
- Acceptance: on the developer's yes: a hard-link snapshot, 5.1's proof (its list of unproven points read), the dry run, the remake, then `status`, the drawable points and `verify` compared with the snapshot. Work dir 2 the same, if its records hold points.
- **Update work dir 2** (the developer, 2026-11-09: a task for later, on order, not now): back up its copy of the Decay card and delete its `HeavyIon:SigFitNGen = 0` line, as in the Decay fixture (answer A). It has no records, so nothing is remade.
- Check: the comparison files are equal; `verify` is clean.
- Blocked by: 5.2, and the developer's yes.

## Log
