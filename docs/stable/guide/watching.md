---
id: watching
summary: looking before running, subsets, reruns, following a job, and a Run's record as a config
code: framework/runner/cli.py, framework/runner/watch.py, framework/runner/record.py
---

# Watching, subsets and reruns

| You want | Type |
|---|---|
| to look before running | `heimdall run CONFIG CFG --plan` |
| what would rerun, and why | `--why` |
| each value and where it came from | `--show-config` |
| a subset | `--points 27x920_MSTW08lo,pdf=NNPDF23lo,3` (names, tags, `q=tag`, indices) |
| fewer events, once | `--set errand.events=50000` (dotted keys, in the file's names; repeatable) |
| a finished point again | `--rerun` (with `--points` for one) |
| only the pages | `--only plot`, or `heimdall plot CONFIG CFG` |
| no pages after this job | `--no-plot`, or `[errand] plot = false`; `plot = ["totality", …]` draws those sets only |
| a Run's pages as it ran | `heimdall plot <A>/<E>/<R>` |
| only the post or pre tools | `--only post`, `--only pre` |
| plain lines (logs, CI) | `--plain`, automatic when not a terminal |
| to follow a job | `heimdall watch [CONFIG [CFG]]`, `--pid N`, `-i N`; a `--journal` job's: `--file …` |
| to pause, and go on later | `p`; later `heimdall runs --resume N` |
| to leave a job running | `d`; or start with `--detach` |
| to stop one from elsewhere | `heimdall stop [CONFIG [CFG]]`, `--pid N` |
| live jobs | `heimdall runs`; `--forget N` drops a pause |
| recent jobs of any state | `heimdall runs --5`, `--10`, `--20`, `--50`, `--week`, `--month` |
| a name for a Run | `--tag nlo`, a configuration's `tag`, or later `heimdall tag <A>/<E>/<R> nlo` |
| a desktop notification at the end | `[errand] notify = "desktop"` |
| a point faster | `shards = K` on Rivet; more Pythia threads alone do not help |
| many points faster | `parallelism = K` or `"auto"` |

The identity covers cards, argv, binaries, analyses and plugins, events and threads. So a rerun of an unchanged point does nothing, and a changed one reruns by itself. `--set cfgs.pdf.threads=8` makes every point "to run". A changed configuration under a serial you set is refused rather than overwrite: bump it, or `--rerun`.

## A Run as it was: its record

Each Run keeps what its points ran with: `records/<A>/<E>/<R>/config/` holds the errand file, its imports and cards, with `snapshot.toml`. A record goes wherever a config does:

```bash
heimdall plot Demo/jets/01_pdf       # its pages: every point it recorded
heimdall status Demo/jets/01_pdf     # complete, or what changed since
heimdall run Demo/jets/01_pdf        # what it misses, with the cards it ran with
```

- **Your configs may move on.** Comment out half the PDFs, edit a card, rebuild the stack: the record still draws all its points. A drawing plans no tool, so it needs no stack but Paint.
- **Restyle it alone:** edit `results/<A>/<E>/<R>/plot.toml`'s `[plot]` and draw again, or use another file's: `heimdall plot Demo/jets/01_pdf --plot Demo/talk_pages`.
- **The live config draws what was recorded too:** `heimdall plot CONFIG CFG` draws its newest Run from its document. When the config's `[plot]` differs, it says so; `--style-sync` takes the config's.
- **A job that runs the same Run again replaces its record,** and says when recorded points are no longer in the config. A serial of its own keeps a Run whole.
- **A tag** is your short name for a Run (`nlo`, `run2.v1`), shown by `runs`, `status` and reports. Never part of an identity.
- **A record from before plot documents** gets one when first drawn; `heimdall migrate --plot-docs` writes all. **From before snapshots:** `heimdall migrate --snapshot <A>/<E>/<R>`.
