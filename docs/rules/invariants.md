---
id: invariants
summary: what must never happen in this repo and on this machine, and why; read before acting
---

# Invariants

Each of these comes from something that went wrong, or from the developer's word. They bind until the developer changes them.

## Ask first

- **Rebuilding `App_Pythia`, `App_yd2rt`, a module program or a Rivet plugin.** A binary's hash is in every identity that ran it, so every such point reruns. Paint is plot-only and safe. See [identity](../stable/internals/identity.md).
- **Changing what an identity or seed hashes:** `record.identity_parts`, `record.seed_basis`, what a tool folder puts in its parts. Every point it touches reruns, which costs generations.
- **A download.** Name its file, source and size before fetching.
- **Writing into a work dir** that is not a test's scratch. Work dirs hold the developer's studies.
- **Pushing.** Never without being asked.
- **A change to `tests/reference/`.** It is a physics change, and it is never regenerated.

## Never

- **Never rewrite Himinbjorg's live state:** `machine.toml`, `recipes.toml`, `toolkits/`, `tools/`. Back up any live file before changing it. `workdirs.toml`, `runs/` and what is built (`base/`, `stack/`, `apps/`) are live too, read by every checkout; `forge/` is disposable but for `forge/downloads/`, a 3.3 GB cache.
- **Never `git clean -x`** while a checkout may hold an un-adopted stack (`stack/`, `env/venv/`, `framework/Apps/`): hours of building.
- **Never `git commit -a`, `git add -A`:** stage named paths. Other sessions' work may be in the tree.
- **Never name a real study** in Heimdall's docs or history: say "a real study's work dir".
- **Never name a real work dir in a test.**

## Machine

- **Go light:** `taskset -c 0-5 nice -n 10`. ROOT's and Rivet's compilers take about 3 GB each, and a heavy build has taken the lab PC down; `root_cores` bounds them.
- **Start a long build detached** (`setsid nohup … < /dev/null &`), or a session's end kills it.

## Tests

- **Tests write only `forge/scratch/`**, through the `HEIMDALL_*` root variables `tests/conftest.py` sets.
- **One pytest session at a time:** the basetemp is wiped per session. The slow suite runs alone.
- **Run pytest directly,** with the stack loaded (`source gjallarhorn.sh`). `make test` runs `make all`, which rebuilds the machine's apps.
- **Fixtures change only together with the test that needs the change.**
- **A fake in a test has the real type.** Tuple fakes once hid a `TypeError` in every setting sweep of three tools.
- **If a test run fails or is interrupted, restore nothing.** Report the state and wait.
