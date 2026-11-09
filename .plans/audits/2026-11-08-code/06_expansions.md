# Expansions

Features the code is one step from, and the ones the use (12-hour runs, sweeps, several Runs of an Errand, a lab PC reached over ssh) asks for. These are proposals: each needs the developer's yes and a plan before code.

## Findings

### E-1 A queue that survives a reboot · Consider · closed 4.1 (first half: `--queued-to` on a queued run is in Postponed)
See [O-3](05_oversights.md#o-3). `heimdall runs --resume-queue N`, and `heimdall runs --queued-to M` on an already-queued run, which moves it in or between queues. The entries already hold `queue` and `queued_to`, so both are a client-side walk of `runs.queue_of` plus `queue_run`.

### E-2 Notifications that reach someone who is not at the desk · Consider
`cli.notify` (`cli.py:1345`) is `notify-send` only, so it needs a desktop session. A detached run started over ssh, which is the lab PC's case, never notifies. Its verdict map (`{0: "done", 1: "a point failed", …}`, `cli.py:1350`) is a fourth list of states ([G-1](04_design.md#g-1)).
**Proposal:** `[errand] notify = "desktop" | "command"`, with `notify_command = ["…", "{verdict}", "{run}"]` run on the end. The user chooses the service (mail, ntfy, a chat webhook), so Heimdall sends nothing outward by itself. The verdict comes from `runs.State`.

### E-3 `heimdall plan` (I-36, decided) · Consider
`--plan` and `--dry-run` are run's flags (`cli.py:50`), and `plot` takes `--plan` too. I-36 decided a command of its own. Today's `--plan` cannot say what a run will cost.
**Proposal:** with E-4, `heimdall plan CONFIG` prints the points, which are complete or in the library, the estimated time (from earlier points' attempts: `record.attempts` holds their durations) and the disk use.

### E-4 Cost estimates from the records · Consider
Every attempt records its duration, and every product its size. Nothing uses them to predict. The developer's runs take 12 hours, and knowing that before starting is the most useful line `--plan` could print.
**Proposal:** `record.estimate(plan)` gives the median duration and size of complete points with the same tools and events, scaled by events. Shown in `--plan`, `heimdall runs` (an ETA for a running run) and `status`.

### E-5 The library beyond generation points · Consider
The library pools generation points only, per Assignment (`points-library` plan, assumption 6). Two kinds of reuse are left:
- **Combine groups and post stages.** Rivet's merged replicas are as expensive to remake as they are cheap to key.
- **Across Assignments.** The key is physics, not the Assignment, so the same Pythia point in two Assignments is generated twice.

**Proposal:** a phase each, after the library has run on a real work dir (I-121's adopt is waiting).

### E-6 A two-way watch socket · Consider
`events.Hub` serves and never reads ([G-5](04_design.md#g-5)). With G-5's one ask channel, the socket could carry the same asks (pause, jobs, stop), so `watch -i` over ssh port-forwarding, or a future web view, controls a run without signals. That needs the same peer-credential check the socket already applies.

### E-7 Static types where the state is · Consider
I-13 (ruff, mypy) and [G-3](04_design.md#g-3) and [G-4](04_design.md#g-4) together: start mypy on `runs.py`, `record.py` and the new `RunEntry` and `RunRequest`. That is where a wrong key costs most.

### E-8 `heimdall du` · Consider
`clean` removes what no plan uses. Nothing says where the space is. One command for the sizes of `records/`, `results/`, `.cache/` and the library, per Assignment and per Run, with what `clean` and `library prune` would free.

### E-9 `--json` on every read command (I-37) · Consider
`show`, `diff` and `score` have `--json`. `runs`, `status`, `ls` and `library list` do not, so a script or an AI in the work dir parses text. The client context (`docs/client/CONTEXT.md`) is written for an AI reader, which would use them first.

## Sweeps still to run

- **What users do by hand.** Read the developer's work dirs' shell history and notes (read only, with their yes) for commands repeated in sequence: each sequence is a feature request.
- **Errors without a way on.** `HeimdallError` raised without `hint`: each is a place where a command could offer the next step.
- **Commands without `-i` or `--json`.** For a consistent surface (I-70).
