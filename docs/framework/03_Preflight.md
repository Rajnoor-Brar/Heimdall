# 03 — P0: Preflight

**Goal.** Know the machine, choose its annex, have Heimdall cloned and recorded, and bring back what
was kept before the wipe. After P0:
- `$HEP/.setup/` exists;
- `state.toml` holds `[machine]` and `[source]`;
- `kept/` holds the user's copies.

**Reads:** [01](01_Target.md) §8 (what was kept), [02](02_Agents.md) §3 (the state).

**Writes:** `$HEP/.setup/` only.

**Gates:** sudo, only if `git` or `curl` is missing. The stack's build needs no sudo: it makes a conda
base first (the compilers, the libraries, Python; [recipes/README.md](../../recipes/README.md) §4).

---

## S1: the machine and its annex

**Preconditions:**
- The start prompt was given in `~/Github/Heimdall` (02 §11.1).
- `git -C ~/Github/Heimdall status --porcelain` prints nothing.

**Tasks:**

1. Create the state's folders:
   ```bash
   export HEP=${HEP:-$HOME/Github/Heimdall}
   mkdir -p "$HEP/.setup/kept" "$HEP/.setup/verify"
   ```
2. Survey, and write `[machine]` into `$HEP/.setup/state.toml` with 02 §3.1's keys, from:
   ```bash
   . /etc/os-release && echo "$PRETTY_NAME"          # os     (macOS: sw_vers -productVersion)
   uname -m                                          # arch
   python3 -c 'import os; print(os.cpu_count())'     # cores (logical)
   awk '/MemTotal/ {printf "%d\n", $2/1048576}' /proc/meminfo      # ram_gb
   df -BG --output=avail "$HEP" | tail -1            # disk_free_gb
   sudo -n true 2>/dev/null && echo yes || echo "ask"                # sudo: "ask" means a password is needed (fine)
   curl -sI --max-time 10 https://root.cern | head -1                # network
   docker info >/dev/null 2>&1 && echo usable || { command -v docker >/dev/null && echo "installed, no group" || echo absent; }
   command -v apptainer && apptainer --version
   python3 --version; git --version
   ```
3. **Choose the annex** by the first rule that holds, and record it as `annex`:

   | When | Annex |
   |---|---|
   | the user's start prompt names one | that one |
   | macOS | `macos` |
   | Linux with `apt-get` and sudo (a password is fine) | `ubuntu` |
   | Linux without sudo | `cluster` |

   `container` is only ever chosen by the user, because it is a way of shipping Heimdall, not a kind
   of machine.
4. Read `targets/<annex>.md`. Its **prerequisites** must hold before S2: the tools P0 and P1 need
   before the stack exists (`git`, `curl`, `python3` ≥ 3.11; `venv` only for `base=system`). A
   missing one on `ubuntu` is a **gate**:
   ```bash
   sudo apt-get install -y git curl
   ```

**Verification:**

| # | Command | Expected |
|---|---|---|
| R1 | `python3 -c "import tomllib; m = tomllib.load(open('$HEP/.setup/state.toml','rb'))['machine']; print(len(m))"` | `12` (the keys of 02 §3.1) |
| R2 | `python3 -c 'import sys; print(sys.version_info >= (3, 11))'` | `True` |
| R3 | `df -BG --output=avail "$HEP" \| tail -1 \| tr -dc 0-9` | ≥ `60`: the lab set used 19.9 GB on the lab PC (installs 6.0, sources 5.6, build trees 6.8, venv 1.5), plus the base (about 2.3 GB, and 0.3 GB of pixi's cache), MadAnalysis5 and room for results |
| R4 | `test -f $HEP/docs/framework/targets/$(python3 -c "import tomllib; print(tomllib.load(open('$HEP/.setup/state.toml','rb'))['machine']['annex'])").md && echo ok` | `ok` |
| R5 | `python3 -c 'import os; print(os.cpu_count())'` and the RAM, against the lab PC before the wipe: 24 logical CPUs, 15 GB | recorded; a smaller machine is not a failure, but P1's `cores` and `root_cores` follow it |

**On failure:**
- R3 below 60: stop. This is a gate; propose `packages=core` (no Geant4 data, ~4 GB less) or
  another disk.
- R2: the annex's prerequisites.

---

## S2: the source and the kept files

**Preconditions:** S1 `done`.

**Tasks:**

1. **Record the revision** the setup starts from:
   ```bash
   git -C $HEP rev-parse HEAD                       # → [source] revision
   git -C $HEP log --oneline | wc -l                # recorded
   ```
2. **Bring back the kept files.** Copy them from where the user put them (the start prompt's
   `<path>`) into `$HEP/.setup/kept/`, keeping their layout:
   ```
   kept/datasets/  kept/literature/  kept/cross_machine/  kept/reports/       (the user's)
   kept/downloads/ (optional: the stack's tarballs, used by 04 S2)
   kept/memory/    (optional: the agents' notes, used by 07 S2)
   kept/reference/output/{cards,config,provenance.json}       (the reference point's output folder, 01 §8)
   kept/reference/results/{<its>.yoda,<its>.yoda.json,<its>.root}   (its results folder; used by 07 S1)
   ```
3. Record `[source] kept` (where they came from) and what was found. A missing optional item is
   noted, not a failure.

**Verification:**

| # | Command | Expected |
|---|---|---|
| R1 | `git -C $HEP rev-parse HEAD` | equals `[source] revision` |
| R2 | `ls $HEP/docs/framework/*.md $HEP/docs/framework/targets/*.md \| wc -l` | `12` (README, 01–07, the four annexes) |
| R3 | `sha256sum $HEP/.setup/kept/datasets/*.yoda \| cut -c1-16` | `625723465b10ea69` (the same file as `tests/fixtures/work/datasets/jets_data.yoda`) |
| R4 | `sha256sum $HEP/.setup/kept/reference/output/cards/pythia.point.cmnd \| cut -c1-16` | `51d0db61bc8ec901` |
| R5 | `sha256sum $HEP/.setup/kept/reference/results/*.yoda \| cut -c1-16` | `0db5cc2e327680ee` |
| R6 | `du -sh $HEP/.setup/kept/literature $HEP/.setup/kept/reports` | about `98M` and `11M` (the lab PC's, 2026-10-10) |

**On failure:**
- R3–R5 differ: the copy is not the one taken before the wipe. This is a gate: the user looks.
  Without R4 and R5, 07 S1 loses its reference point, though the slow suite's gates remain.
- R2 short: the clone is older than these files. Stop, because the phase files are the plan.
