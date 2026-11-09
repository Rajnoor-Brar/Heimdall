---
id: decisions-run
summary: why a run behaves and records as it does: views, records, logging, pausing, the registry
---

# Decisions: a run

The full account of each is at tag `docs/pre-rebuild`, in `docs/07_Record.md`.

- **V23** `.complete` and provenance live with the record, not the products. Overturned V14. Layout now per V157.
- **V26** One block per finished point in the views. Refined by V156.
- **V32** A view never blocks the run: a terminal that stops reading loses the display, never the supervision.
- **V72** One event stream: every view is a listener, and runtime state stays off disk.
- **V74** `heimdall plot` and `heimdall overlay` each take only their own options; housekeeping commands and the Python kit.
- **V111** Provenance across two repositories: each revision and dirty flag, Heimdall's and the work dir's.
- **V132** Work-dir output is split by lifecycle, with a point lock. Layout now per V157.
- **V149** A run keeps little unless told: a finished point's working folder is trimmed.
- **V156** What a run shows: a heading with when it ended, errors under the progress, not over it.
- **V157** One `records/` tree; points in `points/`.
- **V158** A run's snapshot: a record is a config, and pages come from what was recorded, so a run replots after its cards change.
- **V181** Signals and the watch socket made fit for detached runs: the Ctrl-C ladder.
- **V182** The run registry: what runs and ran on this machine, in Himinbjorg's `runs/`.
- **V183** A run on a terminal is a worker it follows; `--detach`; `heimdall stop`.
- **V184** Cluster submissions are in the registry.
- **V191** The registry reads only your own entries, and never deletes a path an entry names.
- **V195** What a run saves is clean: each line a tool prints is cleaned before it is matched, shown or saved.
- **V200** Every attempt is recorded with its cause, and the run's constants too.
- **V201** A digest of every tool's output: head, tail and every matched line. `--logs` had been 90–99 % counters.
- **V202** `run.jsonl`: a run's own log in its record; `heimdall log`.
- **V203** `filters.toml` gains new kinds; a failed tool is asked for its reason.
- **V204** The plot stage's failures are logged the same way.
- **V221** `heimdall runs` shows running jobs by default.
- **V222** In `watch`, `d` detaches and `q` stops.
- **V223** A Run may carry a tag; it distinguishes Runs when drawn together.
- **V230** `p` pauses: running points end, none more starts; a second press discards them.
- **V231** Live runs by index: `runs`, `watch -i N`, `runs --resume N`.
- **V232** Pausing's review defects fixed: a pause while planning says nothing ran.
- **V234** A combined run's plot stage and a listed row's curve order no longer crash.
- **V235** A resume reads the last record's config snapshot, never the live `configs/`; a missing or unreadable one refuses with the command to run by hand.
- **V236** A sweep is a queue: a chain started on each end, each run its own. A failed predecessor lets the next start, a stopped one holds it; a dispatch in the middle splits the queue. Supersedes V75's pipelined sweep.
- **V237** A queued run is its own waiting worker, not started by its predecessor, so a crashed or killed predecessor still lets it start. The registry keeps one writer per entry, at the cost of a sleeping process.
- **V238** A registry entry and its state are values: logic reads the state's word, the screen its text, so rewording changes nothing a program does. A newer entry is listed and never acted on.
- **V239** A free-text verdict gets the word its exit code gives and prints as written; a finished entry with no verdict, state or listed code is `ended`.
- **V240** `heimdall runs` prints a block a run: records' `<A>/<E>`, ongoing jobs, the commands that fit. Colour is plain SGR codes, not rich, as `[N]` is rich markup. `runs -i` takes a live number or an id.
- **V241** `--jobs`: the cap is an override on the Stopper, so a sweep's later configurations take it; the pool is sized to 256; a signal handler only sets an Event; lowering stops no running point.
- **V242** `heimdall show` reads the record alone and recomputes nothing; σ is what the tools reported. `heimdall log` stays as the shorthand.
- **V243** Record formats are one number for the record files together. `records upgrade` stamps files only, the layout moves staying `migrate --layout`'s; every reader that acts on a record checks it, `show` does not.
