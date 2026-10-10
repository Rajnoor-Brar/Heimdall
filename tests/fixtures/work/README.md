# tests/fixtures/work

The tests' work dir (docs/framework/01_Target.md §5.7): a frozen copy of what the tests load. A test
session syncs it into `forge/scratch/work/` and points `$HEP_WORK` there (tests/conftest.py), so the
tests never read or write a real work dir, and a failure means the code changed, not a config.

- `configs/`: the run TOMLs and cards, frozen from High-Energy's `configs/` at commit `0e05885`
  (2026-10-03). `Demo/ep_validation.cmnd` was never committed there (inproc_validation and
  seed_sweep use it), so its copy is the working tree's of 2026-10-03. One change from that
  commit: `Demo/validation.toml`'s `pdf` values carry `LHAPDF6:`, as V40 requires.
- `modules/`: frozen copies of High-Energy's `modules/` at `split/base` (5e0a913), because the tests
  build Decay.exe, InprocJets.exe and the photo_eic, DecayRiv and particle_spectra plugins.
- `datasets/jets_data.yoda`: High-Energy's (sha256 `625723465b10ea69…`), the one dataset the plot
  tests name.
- `hep.toml`: the marker. The walk-up search skips it (it lies under `tests/`); only `$HEP_WORK`
  finds it.

Change a fixture only together with the test that needs the change. Never sync it from a work dir
wholesale.
