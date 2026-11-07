---
id: live-shadow-root
summary: the tests run on a shadow machine root, and a guard watches the live one
affects: testing
issue: I-10
---

**Now holds:** `tests/conftest.py` builds `forge/scratch/machine/` and sets `HEIMDALL_MACHINE` to it for the session. Its `machine.toml` and `recipes.toml` are the templates (all comments), its `runs/` and `workdirs.toml` its own; `stack/`, `base/`, `apps/`, `venv/`, `stacks/` and `forge/downloads/` are links to the real root's. `HEIMDALL_APPS`, `HEIMDALL_INSTALL` and `HEIMDALL_FORGE` are pinned to the real values first, so the stack, the apps and the identities are as before. A session guard fails the run if the real `machine.toml`, `recipes.toml`, `stack/.stamps/` or the apps' files (size, mtime) changed.

**No longer holds:** the live `machine.toml` and `recipes.toml` deciding what a test keeps and sees. The basetemp is no longer inside the machine root, so a path there is no `{machine}/…`: a test of portable paths puts its records under the work dir, as a run does.

**Decisions:** scratch stays at `<real root>/forge/scratch`; the shadow is a folder in it.

**Stable pages need:** `stable/internals/testing.md`, the paragraph on `conftest.py` and its guards.
