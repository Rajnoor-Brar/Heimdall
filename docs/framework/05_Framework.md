# 05 — P2: The framework built and tested

**Goal.** Heimdall, on its new stack, passes everything it passed on the lab PC's old one:
- its apps built, the C++ tests and the fast suite (S1);
- the slow suite with its physics gates (S2).

The baselines are the lab PC's of 2026-10-10: Heimdall at `c6e7590` and after, against the old
`~/HEP` stack linked in (V105–V113 were tested that way).

**Reads:** the manual's 07 §8 (the gates' numbers), copied here as rows.

**Writes:** `framework/Apps/`, `forge/make/`, `forge/tests/`, `forge/scratch/`; nothing in git.

**Gates:**
- a gate row that differs from its number twice (S2);
- nothing else is expected.

---

## S1: the build and the fast suite

**Preconditions:**
- P1 is verified.
- `source $HEP/setup.sh`.
- `git -C $HEP status --porcelain` is empty.

**Tasks:**

1. `hep build --framework --tests`: the apps (`App_Pythia`, `App_PythiaCheck`, `App_yd2rt`, `Paint`),
   Herwig's repository and the C++ tests.
2. `hep make --framework test`: runs the C++ tests, then `pytest -m "not slow"`, which first builds
   the fixture work dir's modules and plugins in `forge/scratch/work/` (V112). Collect the summary
   line and every skip with its reason (`-rs`).
3. Check that the generated parts of the manual are current: `hep make --framework docs schema`.

**Verification:**

| # | Command | Expected |
|---|---|---|
| R1 | `ls $HEP/framework/Apps/*.exe $HEP/framework/Apps/Herwig/HerwigDefaults.rpo \| wc -l` | `5` |
| R2 | `ls $HEP/forge/tests/*.exe \| wc -l` | `3` (test_kit, test_module_kit, test_status) |
| R3 | `cd $HEP && for t in forge/tests/*.exe; do $t >/dev/null \|\| echo FAIL $t; done \| wc -l` | `0` |
| R4 | `cd $HEP && python3 -m pytest -q -m "not slow" -rs -p no:cacheprovider 2>&1 \| tail -1` | `605 passed`, 0 failed, 0 errors, no skips (the lab PC's, 2026-10-10; more if tests were added since, never fewer) |
| R5 | `ls $HEP/forge/scratch/work/build/Rivet/*.so \| wc -l` | `3` (photo_eic, DecayRiv, particle_spectra) |
| R6 | `git -C $HEP status --porcelain \| wc -l` | `0` (the generated blocks and the editor schema were current; the build wrote only ignored folders) |
| R7 | `git -C $HEP status --porcelain --ignored tests \| grep -v __pycache__ \| wc -l` | `0` (the tests wrote nothing under `tests/`) |

**On failure:** a test that passed on the lab PC and fails here means the machine differs (a
compiler, a library's version). Collect the test's output and the versions of P1 S3; this is a
gate. No test is ever skipped to pass the row.

---

## S2: the slow suite and the physics gates (background)

**Preconditions:** S1 `done`. Nothing else heavy runs: the slow suite uses many cores (02 §8).

**Tasks:**

1. As the builder: `cd $HEP && nohup make test-slow > $HEP/.setup/slow.log 2>&1 &`. Watch for its
   summary (8 min 47 s on the lab PC).
2. Read the gates' outcomes into the rows below. They are the manual's 07 §8, measured on the lab
   PC by these same tests.

**Verification:**

| # | Gate (test) | Expected |
|---|---|---|
| R1 | the whole slow suite: `tail -1 $HEP/.setup/slow.log` | `36 passed`, 0 failed, 0 errors (the lab PC's, 2026-10-10) |
| R2 | App_Pythia at 1 thread against the legacy pipeline (`test_gates_p1.py`) | byte-identical YODAs (0 of 1,530 lines differ); σ = 71,422.158 pb |
| R3 | σ at 4 threads, 100k events (`test_gates_p1.py`) | Rivet's `/_XSEC` against the sidecar's: relative difference ≤ 1e-8 |
| R4 | failure injection (`test_failures.py`) | no hang, the right tool blamed, no `.complete` |
| R5 | Lambda, the module program against the Rivet analysis (`test_modules_p4.py`) | 21 histograms, 3,906 values equal |
| R6 | InprocJets against the chain (`test_modules_p4.py`) | all 17 objects equal bin for bin at 1 thread; σ equal at 4 threads |
| R7 | sharded against unsharded (`test_gates_shards.py`) | raw sums and σ equal to 1e-9 |
| R8 | four Rivets on threads against one (`test_modules_p4.py`) | every raw sum and final bin equal; σ equal |
| R9 | replicas combined (`test_gates_combine.py`), points in parallel (`test_gates_parallel.py`) | as the tests assert |
| R10 | Delphes, Sherpa, Herwig (`test_generators_p4.py`); MadGraph, Whizard, three generators (`test_process_generators_p4.py`) | as the tests assert (07 §8's numbers) |

**R2 on a new compiler.** R2 compares against `tests/reference/legacy_run`, which was produced on
the lab PC with GCC 13 and its libm. A newer GCC, or a newer glibc's `libm`, can change Pythia's
floating point in the last bits, and with it the events.
- **If R2 fails while R3–R10 pass**, it is a gate. Report the number of YODA lines that differ, σ
  against 71,422.158 pb, and the largest relative bin difference. Then wait: the user decides
  whether the reference is re-recorded (a new V-row in the record) or the difference is pursued.
- Never regenerate `tests/reference/` without that decision (`CLAUDE.md`).
