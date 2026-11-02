---
id: testing
summary: the test suites, how they isolate themselves, the gates, and what holds the docs
code: tests/conftest.py, tests/support.py, tests/runner/helpers.py, pytest.ini
---

# Testing

Run with the stack loaded, one session at a time: `taskset -c 0-5 nice -n 10 python -m pytest -q -m "not slow"`. The slow suite (`-m slow`) alone. See [invariants](../../rules/invariants.md).

| Suite | Holds |
|---|---|
| `tests/runner/` | the runner, fast |
| `tests/integration/` | real processes: App_Pythia, App_yd2rt, Paint, the plot stage, failure injection; the gates |
| `tests/cxx/` | `Status.hh`, `Kit.hh`, the module kit |
| `tests/fixtures/work/` | the tests' frozen work dir |
| `tests/support.py`, `tests/runner/helpers.py` | `support.heimdall` runs `heimdall` in the scratch work; `helpers.raw(**changes)` (dotted keys as `__`), `parse`, `plan` |
| `tests/reference/` | **data only**: the legacy pipeline's cards, base card and YODAs, and `point_counts.toml`. The gates compare against it |

## Isolation

`tests/conftest.py` syncs the fixture into `forge/scratch/work/` (its `build/` kept), sets `HEIMDALL_WORK`, `HEIMDALL_RESULTS`, `HEIMDALL_RECORDS`, `HEIMDALL_CACHE`, `HEIMDALL_REPORTS`, `HEIMDALL_WORKDIRS`, `HEIMDALL_RUNS` into `forge/scratch/`, and `HEIMDALL` to this checkout, unconditionally. The basetemp is `forge/scratch/pytest/`.

With the stack loaded, the session runs `make all` in the scratch work once, since planning reads a plugin's `.info`. The `work_built` fixture is that build, or a skip; every `slow` test has it. A session guard fails the run if `tests/fixtures/` or `tests/reference/` changed.

Use the `scratch` fixture for files. A test needing its own work dir makes one there and points `HEIMDALL_WORK` at it, calling `paths.reset()` around the change.

## What to keep

- Tests that prove a refusal still refuses (a FIFO into Delphes, an undeclared option).
- A test that needs a tool skips cleanly when it is not on `PATH`.
- **L26** A test whose fakes have another type than the real thing hides bugs: Sherpa, Whizard and MadGraph sweeps crashed while their tests passed.
- **L17** Reading a YODA resets `LC_ALL` to `C`, and `make` runs in an ASCII locale: name the encoding everywhere.

## The docs are tested

`tests/runner/test_docs.py` holds [writing](../../rules/writing.md): links, TOML examples loaded through the real parser, every setting documented, generated pages current, frontmatter, caps, every id and `doc:` code cites resolves. Change a key, and the test says what to update.
