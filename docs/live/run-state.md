---
id: live-run-state
summary: a run's state is a value (runs.RunState: a word and its qualifiers), so logic reads the word and the screen prints the text
affects: live-runs
issue: implementation round 1
---

**Now holds:** `runs.state_of(entry, live)` returns a `runs.RunState`. Logic reads its `word`, one of `runs.STATES`; the screen prints its `text`, which is exactly what `runs.state()` has always returned (`done, resumed`, `running (not reachable from here)`, `exit 3`, `on <host>`). The word comes from the entry's fields, never from display text: its `state`, else the first part of its `verdict` when that is a word of `STATES`, else the verdict its exit code has, else `exit`.

- `STATES` adds `forgotten`, `exit` and `unknown` (a run on another host or PID namespace) to the words `heimdall runs --state` took. `--state forgotten` lists a run that left its queue unrun; `--state "not run"` lists a verdict that is `not run: <message>`; a paused run that was forgotten is `paused`.
- A queued run's turn is `RunState.gives_turn` (`GIVES_TURN`, and any finished state but a stopped or paused one) and `RunState.holds` (`HOLDS`, and a paused run that was forgotten). A plain pause is waited for.
- The listing's colours, `--state` and the prompt's keys read the word.

**An entry is a value.** `runs.entry()` and `runs.entries()` return `runs.RunEntry`, parsed once from the entry file: typed fields for every key a run writes, its queue keys as `entry.queue` (`queue_id`, `queued_to`, `queued`, `held`, `began`, `left_queue`, `dispatched_from`), and `extra` for any key this version does not know. `entry.as_dict()` gives back the dict it was parsed from, key for key. Readers (`state_of`, `alive`, `queue_of`, `paused`, `again`, the listing, the `runs` actions) take a `RunEntry`; writers (`runs.update`, `finish`, the Recorder) still write dicts, one field at a time.

**No longer holds:** `house.state_word`, which cut a state's text back to its first word, and `house.RUN_STATES`.

**Decisions:** a verdict that is free text (`the runner failed: …`, `killed by signal 9`) has the word its exit code gives (`not run`, `exit`) and prints as it was written. A finished entry with no verdict, no state and an unlisted code is `ended`.

**Stable pages need:** `internals/live-runs.md` (the state's shape and the word list).
