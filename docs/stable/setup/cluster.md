---
id: cluster
summary: Heimdall on a cluster without sudo: an image or a user-space build, filesystems, what has been proven
code: framework/runner/cluster.py, framework/runner/image.py
---

# On a cluster

| Way | When | How |
|---|---|---|
| **A. An image** (preferred) | Apptainer or Singularity is installed | build elsewhere ([images](images.md)), copy the `.sif` over |
| B. A user-space build | no Apptainer | the conda base brings compilers and libraries with no sudo: `git`, `python3` ≥ 3.11 (`module load python/3.11`), glibc ≥ 2.28; `graphics=OFF`; `geant4_data=OFF` with no network on the build node |

`heimdall cluster` plans every point on the login node, outside any image (there is no `sbatch` inside it), so Slurm through an image still needs Way B's environment on the login node. `[cluster] image` moves only the jobs. Module lines go in `setup_extra`. Using it: [scale](../guide/scale.md).

- **Filesystems:** `records/`, with `.complete` markers and logs, stays on the shared filesystem, as the finish job reads it. FIFOs and prepare caches' `flock` work on NFSv4 and Lustre (mounted with `flock`). One refusing `mkfifo` fails the point at its start: use files for that chain.
- **The nodes run the login node's binaries:** same OS and architecture.
- **`$HEIMDALL` shared by several users:** read-only for them, each with their own work dirs.
- **`heimdall watch`** sees only runs on one node; `--status` and logs stand in. `heimdall runs` lists submissions. A detached `heimdall run` is refused in a Slurm job, and ends with an `salloc` allocation.
- **Another batch system** (HTCondor, PBS): not yet. Submit a script that runs `heimdall run` inside one allocation, sized with `--set errand.threads=$SLURM_CPUS_PER_TASK`.

**Proven so far:** `heimdall cluster` has run against an emulated Slurm only, and Way B has never run. Expect a failure per missing library.
