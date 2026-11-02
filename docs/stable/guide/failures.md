---
id: guide-failures
summary: what to do when a point fails, and what each common refusal means
code: framework/runner/execute.py, framework/runner/config.py
---

# When something fails

The job goes on to the next point, and the point's block names the tool to blame. Then:

1. Read `records/…/logs/<point>/<tool>.log` (and `<tool>.prepare.log`, `prelim.log`): its first 100 lines, every line its rules matched, its last 200. Earlier attempts are in `history/<n>/`. For a tool's whole output, run again with `--logs`. `heimdall log <A>/<E>/<R>/<point>` prints the point's attempts and digests; `heimdall log <A>/<E>/<R>` the Run as it printed itself.
2. A product that failed its checks keeps its `.partial` name, and the point has no `.complete`, so it runs again next time.
3. *"rivet analysed N events; the producer wrote M"*: the chain broke mid-stream. Look at the generator's log first.
4. *"… was silent for 300 s, since 20:29 (integrating; last line: "…")"*: a stall. Raise `stall_after` if it is legitimately quiet.
5. Fix it, then `heimdall run … --points <that point>`. Complete points are skipped anyway.

More to look at: `--plan` shows exact argv and cards; `--journal` writes every event to `status.jsonl`; `--keep work` keeps a finished point's whole folder; `provenance.json` records every binary and card.

`heimdall run` exits 0 when everything is done, 1 when a point, stage or page failed, 2 for a config error (nothing ran), 6 when stopped or paused (the same command resumes).

## Common refusals

| Message | Means |
|---|---|
| `[quantities.X] is set but no tool in this chain consumes it` | nothing would change with X: give it a `to`, or drop it |
| `'delphes' cannot read a FIFO` | put Delphes in a later group, so it reads a file |
| `FIFO 'x' connects A and B across groups` | put A and B in one group, or use a file |
| `'photo_eic' does not declare the option X` | the option is not in the analysis's `.info` |
| `the PDF set 'X' is not installed` | `lhapdf install X` |
| `'…' is TLatex; labels are LaTeX` | write the LaTeX the hint gives, or `heimdall migrate` the file |
| `[plot.overlay] is a figure now` | `[plot.figures.<name>] class = "overlay"`, or `heimdall migrate` |
| `base config not found` | the card is not beside the errand file naming it; write `./path` for elsewhere |
| `$HEIMDALL_APPS/App_Pythia.exe is not built` | `heimdall build --framework` |
| `not inside a work dir` | `cd` into one, or `heimdall setup <dir>` |
| `'event_count' is the v2 form: this file is v3, where it is events` | write the v3 name, or `heimdall migrate --v3`; names: [legacy](../../reference/legacy.md) |
| `… made from other inputs; running would overwrite them` | your configuration changed under a serial you set: bump it, or `--rerun` |
