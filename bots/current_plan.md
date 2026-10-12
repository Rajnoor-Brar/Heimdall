# Current plan

**What is open:**
- [docs/audit_2/01_Health.md](../docs/audit_2/01_Health.md): findings H1–H16 and phases R0–R3, each
  step only on the user's order.
- The decisions are in docs/07_Record.md, and finished task logs in [archive.md](archive.md).

**Finished, and in git:**
- audit 1 (V52–V89, `git show 3a5ec16:docs/audit_1/06_Plan.md`);
- the figures (V80–V89);
- the manual's rebuild (V90–V92, `git show 3a5ec16:docs/audit_2/02_Manual.md`).
- `[config]` (V93–V97): it replaces `[master]`; `import` nests, crosses projects and takes `only` a part; `drop`; `vars`; `meta` (version warnings). The doc is 04 §3.
- `[run.cfgs.<cfg>]` (V98–V100): configurations moved out of `[run]`; `[run]` gives every configuration its keys (`[run.defaults]` gone); an import's location rule is per folder.
- Decks, `hep deck` (V102–V104, docs/reporter, 2026-10-10): `figures/layout.py` (sheets and composites: pdflatex, PNG by pdftoppm), `runner/deck.py` (blocks from result folders or a folder's files; composites; deck.md through pandoc to Beamer, pptx, dzslides HTML, an Overleaf zip), `runner/viewer.py`; the manual's 03 §11, 04 §15, 05 §1.8.

## Now

**Heimdall (2026-10-10):** split from High-Energy at `split/base` (5e0a913) and built here, in its own
repository at `~/Github/Heimdall`, on the old lab PC's stack. Since V122 the machine root
`~/Himinbjorg` holds it: `stack` and `venv` are links to `~/HEP/install` and `~/HEP/.venv`, and `apps/`
and `forge/` are real folders there.
- **Done:** the seed (`99da1d3`), the recipes and toolkits (`@primary` = the lab set plus
  MadAnalysis5; isolated C++20 stacks), the seam (two roots, `hep setup`/`hep where`, the build split
  on `framework/rules.mk`, provenance across both repositories, portability), the tests on the
  fixture work dir, the manual re-rooted (V105–V113), and
  [docs/framework/](../docs/framework/README.md) rewritten as the fresh-machine runbook (P0 Preflight,
  P1 Stack `@primary`, P2 Framework, P3 Work dirs, P4 Verify).
- **Numbers here:** `hep build --framework` 4 s; 3 C++ tests pass; fast suite 629 passed; slow suite
  37 passed (about 9 min, the byte-identical legacy gate and the emulated cluster included); `test_stack_build` 27; the
  starter in a scratch Top-Quark: 2 points, 35 pages, 9 s.
- **Next, the user's:**
  - publish Heimdall (a gate: a private `Rajnoor-Brar/Heimdall`), or keep a bundle;
  - before the reinstall, 01 §8's checklist (Heimdall's bundle or push; High-Energy pushed; the
    kept files and the reference point);
  - on the new machine, the runbook from 02 §1.
- **`hep cluster` (2026-10-11, V114):** a configuration as Slurm jobs (pre job → points array →
  finish job, each an ordinary `hep run --stages …`), `[cluster]` in hep.toml, the run TOML, the
  configuration, `--set`. Tested against an emulated Slurm only: the first real submission (on a
  cluster the user has) is a by-hand check, `--dry-run` first.
- **The fixture holds no study by name:** the projects are `Demo` (ep jets, the
  validation against ZEUS 2012, the generators), `Decay` (Λ → p π⁻) and `Generators`; the physics
  and the frozen references are as they were.
- High-Energy itself is untouched (only the tag `split/base` was added); its conversion to a work
  dir is parked (06's appendix).

Otherwise nothing is in progress. Waiting on the user:

- **Audit 3** (2026-10-12, [docs/audit_3/](../docs/audit_3/README.md)): a user-experience audit after the
  first Mac build (U1–U66). Remediation in seven phases (06_Plan.md: build reliability,
  verification/`hep doctor`, the machine root `$HEP_MACHINE` and the shell, one tool system, the work
  dir's lifecycle, schema v3, the CLI and first run). Nothing built until the user orders a phase.
  The Mac build's notes and `check_stack.sh` are in the ignored `.setup/`.
- **R0:** verify the mpl pages against mkhtml's, after which the yoda backend goes (H11).
- **R1–R3** of the health check: quick fixes (a compare figure drawn once, H2), then structure
  (`runner/figures.py`, the figure-class rules in the schema), then sheets, tests and docs.
- **`hep migrate --stamp`** (the [config] plan's optional C3 S3): it would write the stack's versions into `[config.meta].versions`. Only if wanted.
- **Later**, on the user's word:
  - F8 `--more`;
  - HTCondor and PBS for `hep cluster` (Slurm is V114); an Apptainer image for its jobs;
  - Paint's PDF line widths (about 2× too thick);
  - the held C++/Rivet items (K3, K4, K7, K8, K10, yd2rt's dead parameter);
  - `extends`/`common.toml` for validation ("not now").

## Standing constraints

- **Commits:**
  - local, never pushed without the gate, with the Co-Authored-By line;
  - stage named paths only, never `commit -a`; the stack lives in `~/Himinbjorg`, outside the tree.
- **Tests:**
  - tests run in the fixture work dir's copy, `$HEP_FORGE/scratch/work/` (V52, V112), never a real one;
  - one pytest session at a time, and the slow suite not while the user's long runs share the cores;
  - `source setup.sh` (this Heimdall's) before make or pytest.
- **Approvals:**
  - the stack (`~/Himinbjorg`'s `stack/`, `venv/`; here, links to `~/HEP`) and downloads need the user's
    approval; never write into `~/HEP` or its venv;
  - a rebuilt App_Pythia, App_yd2rt, InprocJets or Rivet plugin changes the identity of every point
    that ran it, so ask before rebuilding (Paint is plot-only and safe).
- **Docs:** after changing a schema key's `doc`/`notes`, base.toml's comments or the CLI's help, run
  `hep make --framework docs schema`.
- **Way of working:** never implement without an explicit order; plans first, questions when a
  request is ambiguous.
