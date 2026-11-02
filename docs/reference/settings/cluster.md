---
id: settings-cluster
summary: every key of [cluster], for running a job on Slurm
code: framework/schema/run.toml
generated: true
---

Generated from the code; change it there. `heimdall explain <key>` says the same.

# `[cluster]`

[`scheduler`](#scheduler) · [`time`](#time) · [`partition`](#partition) · [`account`](#account) · [`qos`](#qos) · [`constraint`](#constraint) · [`gres`](#gres) · [`memory`](#memory) · [`cpus`](#cpus) · [`max_running`](#max_running) · [`mail`](#mail) · [`setup`](#setup) · [`image`](#image) · [`sbatch`](#sbatch) · [`pre`](#pre) · [`finish`](#finish)

## `scheduler`

| Type | Default | Acceptable |
|---|---|---|
| string | `"slurm"` | `"slurm"` |

The batch system `heimdall cluster` submits to: `"slurm"` (`sbatch`, `squeue`, `sacct`, `scancel`), the only one so far.

## `time`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

Each job's wall-time limit, as `sbatch --time` takes it (`"02:00:00"`, `"1-00:00:00"`): one point's, for the points; **required** in one of the layers, because a site's default limit is a surprise `TIMEOUT`

## `partition`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

`sbatch --partition`; unset: the site's default.

## `account`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

`sbatch --account`; unset: the user's default.

## `qos`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

`sbatch --qos`

## `constraint`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

`sbatch --constraint`, the nodes' features (`"avx2"`)

## `gres`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

`sbatch --gres` (`"gpu:1"`)

## `memory`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

`sbatch --mem` per job (`"8G"`); unset: the partition's default.

## `cpus`

| Type | Default | Acceptable |
|---|---|---|
| integer | `0` | at least 0 |

`sbatch --cpus-per-task`; `0`: the costliest point's cores, as `--plan` counts them (its generator's `threads`, a sharded tool's shards, an integrated program's threads and one more)

## `max_running`

| Type | Default | Acceptable |
|---|---|---|
| integer | `0` | at least 0 |

The points array's throttle, `--array=1-N%K`; `0`: as many as the scheduler gives. `parallelism` is not used: each job is one point.

## `mail`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

`sbatch --mail-user`, with `--mail-type=END,FAIL`

## `setup`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | `[]` | — |

Shell lines each job runs first, before it sources Heimdall's `gjallarhorn.sh` (`"module load gcc/13"`): what the nodes need that the login shell had.

## `image`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

The image's own Heimdall and stack run the job (`apptainer exec --cleanenv`, or `singularity`), with the work dir bound at its own path; `setup` still runs first, on the node (`"module load apptainer"`). `heimdall image build` makes one.

## `sbatch`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | `[]` | — |

Any other `sbatch` options, each as written (`"--exclusive"`, `"--export=NONE"`, `"--reservation=r"`), after the ones the keys above give.

## `pre`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

The resource keys (`time`, `partition`, `account`, `qos`, `constraint`, `gres`, `memory`, `cpus`, `sbatch`) for the pre job only, over the others.

## `finish`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

The resource keys for the finish job only (the combined groups, the post tools and the plots), over the others; its `cpus` default to 1.
