---
id: scale
summary: making a study bigger: more Rivets, several points at once, replicas and combine, seeds, several event counts, Slurm
code: framework/runner/execute.py, framework/runner/record.py, framework/runner/cluster.py, framework/runner/post.py
---

# Scale and statistics

## More Rivets

A Rivet process uses one core, so in a Pythia → Rivet chain it is the limit (about 1,500 events/s with ZEUS_2012), and more Pythia threads only wait for it.

```toml
[tools.rivet]
input    = "pythia"
analyses = ["ZEUS_2012_I1116258"]
output   = "validation.yoda"
shards   = 10                    # 10 Rivet processes, each on a share, merged into validation.yoda
```

Nothing else changes. The events and result are the same as unsharded; the point reruns, since its commands changed. Keep `threads + shards` within the machine's cores. Every analysis must be re-entrant (`Reentrant: true` in its `.info`).

## Several points at once

```toml
[errand]
threads     = 5                  # each point's Pythia threads
parallelism = 4                  # 4 points at a time; "auto": as many as fit
```

Every point gets exactly its one-at-a-time result, and `parallelism` reruns nothing. Each point keeps its own folder. `--plan` prints the estimate, and warns past the machine.

## Replicas, merged

Seeds per curve, merged into one:

```toml
[cfgs.default]
vary    = ["pdf", "replica"]         # 4 PDFs × 5 seeds
combine = ["replica"]                # one curve per PDF: 5× the statistics

[quantities.replica]
to     = { "pythia/seed" = true }    # only changes the seed
points = [{ tag = "s1", value = 1 }, { tag = "s2", value = 2 }, { tag = "s3", value = 3 }]
```

The merged YODAs sit beside the seeds' own folders, and pages are drawn from them. A second configuration with the same vary and no `combine` gets the same seeds and draws each as its own curve: how far one seed wanders. To merge for one figure only, use a [`merged` figure](plots-figures.md).

Or merge once in a post stage:

```toml
[cfgs.replicas]
vary  = ["replica"]
chain = [["pythia", "rivet"]]
post  = ["merge"]

[tools.merge]                        # rivet-merge -e
input  = "jets.yoda"                 # that product of every point
output = "merged.yoda"
```

The post stage runs only when every point is complete, and reruns when any changes.

## Several event counts

`events = [100_000, 1_000_000]` in a configuration is one configuration per count, `<name>_<count>`, run in turn.

## Seeds

By default a point's seeds follow its generator's identity, so one setup always gives the same events. A `Random:seed` in your card is not used, as the runner sets it; the plan says so. To choose:

```toml
[errand]
seed = 3245364                   # "identity" (the default), "random", or an integer; a configuration may say its own

[quantities.seed]                # or one exact seed per point
to     = { "pythia/seed" = true }
points = [{ tag = "1001", value = 1001 }, { tag = "2001", value = 2001 }]
```

- **An integer:** at `threads = 12` the point uses seed … seed + 11. Space varied seeds by at least `threads`: two points of one setup whose blocks overlap would repeat events, so the plan refuses them.
- **`"random"`:** drawn each time a point runs. A complete point keeps its sample; `--rerun` draws again.
- **Repeating a point:** `provenance.json` records its seed. `heimdall reproduce records/…/<point>/provenance.json` runs it again beside the original and compares the products; `--anyway` runs today's setup with the recorded seed.

## On a Slurm cluster

`heimdall cluster` runs a configuration as a pre job, a points array (a task per point to run), and a finish job (combined groups, post tools, plots). Each is an ordinary `heimdall run`, so it skips a complete point and gives the same events. Run it on the login node, with Heimdall and the work dir on a filesystem the nodes see. Every key: [cluster settings](../../reference/settings/cluster.md).

```toml
[cluster]                     # machine.toml or heimdall.toml: this machine's defaults
account   = "my-group"
partition = "standard"
setup     = ["module load gcc/13"]
```

```toml
[cluster]                     # the errand file: the study's
time        = "04:00:00"      # each point's limit: required in one of the two
memory      = "8G"
max_running = 20

[cluster.finish]
time = "00:30:00"
```

```bash
heimdall cluster Demo/jets energy_pdf --dry-run   # write the job scripts, print the sbatch lines
heimdall cluster Demo/jets energy_pdf             # submit
heimdall cluster Demo/jets energy_pdf --status    # each point: complete, running, pending, failed
heimdall cluster Demo/jets energy_pdf --cancel    # scancel the latest submission
```

- A configuration's `cluster = { … }` is over the errand file's, and `--set cluster.time=…` over everything.
- `cpus` defaults to what a point keeps busy. `parallelism` is not used: `max_running` is.
- A second submission is refused while the first still has jobs pending or running (`--status`, or `--cancel`). Scripts and logs are in `records/<A>/<E>/<R>/cluster/<stamp>/`. `heimdall watch` cannot reach a node: the logs and `--status` stand in.
- Each script's last line is the `heimdall run` it makes, which can be typed by hand.
- FIFOs and prepare caches' locks are on the shared filesystem: NFSv4 and Lustre take both.
- `[cluster] image = "<name>"` runs every job in an Apptainer image. `heimdall cluster` itself still plans on the login node, outside it. Setting a cluster up: [cluster](../setup/cluster.md).
