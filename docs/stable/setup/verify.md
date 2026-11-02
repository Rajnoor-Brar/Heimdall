---
id: verify
summary: how to check a new or changed machine: doctor, the support matrix, the tests, and comparing physics against a kept point
code: framework/runner/doctor.py, recipes/verify.py, .github/workflows/stack.yml
---

# Verifying a machine

```bash
source gjallarhorn.sh
heimdall doctor                       # what every package can do; libraries that no longer resolve
heimdall build --framework
taskset -c 0-5 nice -n 10 python -m pytest -q -m "not slow"     # then -m slow, alone
```

- **Each package, as built:** its `[[<package>.verify]]` checks run right after install (versions, features, Python modules, a short run); a failure fails the package. `heimdall doctor` runs them all on demand.
- **The support matrix:** `heimdall doctor --record` writes a machine's row to `recipes/support/`: platform, date, revision, versions, every check that did not pass. `--matrix` prints them. A platform is supported as far as its last recorded run says.
- **CI:** `.github/workflows/stack.yml`, started by hand, builds the container on a clean Ubuntu, then runs `heimdall doctor --quick` and the fast tests.
- **`tests/runner/test_stack_build.py`** checks plans, the full dry run, and the downloader against a local server.

## The physics

To prove a new install matches an old one, keep a reference point's `provenance.json`, cards and YODA, then in a scratch work dir with the fixture's `configs`, `modules` and `datasets`:

1. Plan it with its seed pinned and diff the cards, comment lines aside: `--set cfgs.default.seed=<seed> --points <name> --plan`.
2. Run it. σ and each histogram's entries should match what the provenance says; a different binary means a different identity, so compare numbers, not hashes.
3. A byte difference on a new compiler is a decision to make, not automatically a fault.

Details of a run, and where its numbers live: [provenance](../internals/provenance.md).
