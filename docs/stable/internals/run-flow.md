---
id: run-flow
summary: a run from command to pages: planning, one point, scopes, points at once, several runs, combine, and where each check lives
code: framework/runner/cli.py, framework/runner/execute.py, framework/runner/post.py, framework/runner/tools.py, framework/runner/cluster.py
---

# A run, from command to pages

## Planning writes nothing

`cli.build_plans`, returned as one `cli.Planned`:

1. **Load** (`config.load`): the file and its imports, `--set` applied to the raw table, then checked against the schema: sections, keys, types, figure rules, sweeps, `plot_points`, tool lists.
2. **Expand** (`sweep.points`): the grid of the axes, names from tags, unique names; `--points` picks.
3. **Plan the pre stage** (`post.plan_pre`), then **every point** (`tools.plan_point`): its chain with each `@<quantity>` replaced (`config.resolve_chain`); the active quantities and consumers, each value in its tool's spelling; the interfaces and connection rules; each tool's card, config, prepare key and argv; the context file.
4. **Identity, then seeds**: [identity](identity.md). Then `tools.finalise` writes seed lines into the cards.
5. **Plot checks** (`plot.validate`, `check_texts`, `check_figures`), then the combined and post plans.

With `--plan` it stops here. **Running** (`cli.run_one`): `post.run_pre` → `execute.run_points` → `points.json` → `post.run_combined` → `post.run` → `plot.draw`. A pre failure stops everything; the post stage runs only when every point is complete, because a merge or fit over a subset would look like the whole.

## Scopes

| Scope | What runs | Configured by |
|---|---|---|
| per run, once | load, expand, plan, checks | `[file]`, `[errand]` |
| **pre**, once before every point | a download, a shared build; its identity is in theirs | `pre` |
| **per point** | `[prelim]`, prepare steps, then the chain's groups | `chain` |
| **combined**, once per group | the merge of points differing only in `combine`'s quantities | `combine` |
| **post**, once after every point | merges, fits, any statistics; handed `points.json` | `post` |
| **plot**, once, last | the pages | `[plot]` |

## One point

`execute.run_point`:

1. **Prepare the directories:** write cards and configs; delete an old `.complete` and any product left over; make FIFOs fresh; touch agreed files; run `[prelim]` commands. `execute.prepare` is a point's first write.
2. **Prepare steps** ([caches](caches.md)).
3. **The groups, in order.** Each tool starts at once in its own process group, its stdout and stderr read from pipes, and for a standard-status tool its status pipe. The supervisor polls ([failures](failures.md)). After a group succeeds it **settles**: sidecars of generators that always make what they are asked, then count checks, then products renamed from `*.partial.*`.
4. **Record:** FIFOs removed, `provenance.json` written, `.complete` holding the identity written **last**.
5. **Tidy** (`_tidy`): the working folder keeps `cards/`, `config/`, tool logs and the lock, unless the run keeps `work`.

A failure stops the point: products keep partial names, no `.complete`, the working folder stays whole, and the run goes on to the next point.

## Points at once

`execute.run_points`: points not yet complete run `parallelism` at a time on a thread pool made for `Stopper.CEILING` (`heimdall-point` threads, started as points start; a run at 1 is a pool of one), each emitting to the run's event bus. It reads the cap (`Stopper.cap`) at every dispatch, so `heimdall runs -i N --jobs M` changes it while the run goes ([live runs](live-runs.md)). The main thread waits in half-second steps, so Ctrl-C gets in, and starts nothing more once a stop or pause is set (`Stopper.halted`). `"auto"` is `os.cpu_count() //` the costliest point's cores (`execute.auto_parallelism`).

Shared across points: the event bus and the views it feeds, and prepare cache entries (a lock per entry, `flock` on `<entry>.lock`, the `.prepared` stamp rechecked inside).

## Several runs

`cmd_run` asks `Errand.runs(name)`: the named configuration; else `sweep_runs`'s list or every swept one in file order; else `[errand].run`. It plans all first, so a bad one means nothing runs.

With a terminal or `--detach` they are a queue of workers, one run each, the next waiting for the one before ([run queue](run-queue.md)). Otherwise they run in this process, one after another, each emitting through an `events.RunBus`; one whose planning fails at its turn gets a `not run` pair of events (`cli.not_run`), so `watch.follow_file` never waits on it. There is one `Stopper`, which a stop or a pause reaches.

## On a cluster

No executor of its own: a job is `heimdall run --stages …` on a node (`cluster.py`). The submission plans every point first, so a bad card is refused before any job. A job rechecks its own cards unless the submission kept `cache`. Processes on one tree never rename each other's temporary files: `record.write_atomic` and the card-check cache name theirs by process.

## Combine

`post.plan_combined` plans one stage per group of points differing only in `combine`'s quantities, as `post.plan` plans post: a `Tool` of the `merge` folder, `upstream` set to members' identities, `Point.stage = "combined"`. The plot stage draws the groups as it draws points.

## Where a check lives

| Check | Module |
|---|---|
| C1–C5, C12, C14, the figure rules | `config`, `paths` |
| C7, C8, C10 | `quantities`, `tools._render` |
| C6, C9, C13 | `tools` |
| C11 | `sweep` |
| style, backends, data, bands, figures, texts | `plot` |

Everything raises `HeimdallError`; nothing else prints error text.
