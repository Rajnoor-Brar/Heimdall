# Target: a cluster, no sudo

A university cluster or a remote compute node: Linux, no sudo, maybe Apptainer, maybe environment
modules, maybe no network on the compute nodes. Only what differs from the phase files is here
(D11).

## Two ways, and which to take

| Way | When | How |
|---|---|---|
| **A. The image** (preferred) | Apptainer (or Singularity) is installed | build the image elsewhere (the [container](container.md) annex), copy the `.sif` over, run work dirs through it. P1 is replaced by the image, which also builds Heimdall's apps; P2's tests run inside it |
| B. A native user-space build | no Apptainer, and the user asks for it | `system=false`: every system package must come from environment modules or already be there. P1 S1 lists what is missing; each item is a gate |

P0 S1 records `apptainer` in `[machine]`. With it, propose A at P0's end.

## Prerequisites

- **Way A:** `apptainer` ≥ 1.1, and room for the image (about 10 GB with `packages=all`).
- **Way B:** `git`, `python3` ≥ 3.11 (`module load python/3.11` or similar), a C++17 compiler
  (GCC ≥ 11), `cmake` ≥ 3.20, and the libraries of `apt_packages` under their module names.

## System packages, overlay and launching

| | Way A | Way B |
|---|---|---|
| system packages | inside the image | modules: record the exact `module load` lines in `[choices]`, and put them in `env/machine.sh` through `settings.toml`'s `setup_extra` (`settings.toml`) |
| overlay | none | `system=false graphics=OFF`; `geant4_data=OFF` if the build node has no network (Geant4 then runs only without its datasets) |
| launching | `apptainer exec --bind <work>:<work> heimdall.sif bash -lc 'cd <work> && hep run …'` | `source $HEP/setup.sh` after the module loads |

## Running on a cluster

- **Slurm: `hep cluster`** (V114; the manual's 02 §7.5 and 05 §1.9). From the login node, with Heimdall
  and the work dirs on a filesystem the nodes see, it submits a configuration as a pre job, an array
  of points and a finish job, each an ordinary `hep run --stages …`. The machine's account,
  partition and `module load` lines go in the work dir's `hep.toml` `[cluster]`; `time` (required),
  `memory` and `max_running` in the run TOML's. Way A's image is not wired into it yet: its jobs run
  Heimdall from the shared filesystem (way B, or the image's Heimdall copied out to it).
- **Another batch system** (HTCondor, PBS): not yet. Submit a job script that runs `hep run` inside
  one allocation, and size `threads` and `parallelism` to it (`--set run.threads=$SLURM_CPUS_PER_TASK`).
- **`output/` stays on the shared filesystem** with `hep cluster`: the points' `.complete` markers and
  the jobs' logs are there, and the finish job reads them. `[prelim]`'s FIFOs are made there too;
  NFSv4 and Lustre take them (a FIFO's two ends are on one node). A filesystem that refuses `mkfifo`
  fails the point at its `[prelim]`, saying so: then use files instead of FIFOs for that chain.
- **The prepare caches lock with `flock`** on the shared filesystem: NFSv4 and Lustre (mounted with
  `flock`) honour it.
- **`hep watch`** sees only runs on the same node, in the same network namespace (abstract sockets):
  `hep cluster --status` and the jobs' logs stand in.
- **The nodes run the login node's binaries:** the same OS and architecture.
- **`$HEP` shared by several users:** make it read-only for them. Each user needs their own work
  dirs, and Heimdall's `framework/Apps/` is written only by `hep build --framework`.

## Allowed adjustments (02 §7)

- Way B only: a module name for a library, recorded with its version.

Everything else is a gate.

## Known limits

- Way B has never been run. Expect a gate per missing library.
- `hep cluster` has been run against an emulated Slurm only (its scripts executed locally, in
  chain order); the first real submission is a by-hand check: `--dry-run`, then one small
  configuration, `--status` until done.
- Without network on compute nodes, the PDF sets and Geant4's data must be fetched on a login node
  (P1 S2's downloads gate says where).
