---
id: outputs
summary: what a run writes and where: records, results, reports, cache; what is kept; what may be deleted
code: framework/runner/tools.py, framework/runner/paths.py
---

# Outputs

Each tree has one purpose. **`records/`** is what a run needs while it runs or is launched, and what traces it back. **`results/`** is what matters afterwards. **`.cache/`** is rebuilt on demand, and `rm -rf .cache` is always safe. A run writes nothing else, and nothing in Heimdall.

`<E>` is the errand's name; `<R>` is `NN_<name>`, its serial and its configuration's folder ([paths](paths.md)). `<point>` is the swept tags joined by `_`, or `point`.

```
records/<A>/library/<key16>/   a library point's records (library = true), beside results/<A>/library/<key16>/ its products; index points.jsonl
records/<A>/<E>/<R>/
  points.json           every point's values, products, identity, state
  run.jsonl             the run's own log, every run's        status.jsonl with keep journal
  tag                   the folder's tag and labels (TOML), when it has any
  points/<point>/       provenance.json identity.json .complete attempts.jsonl   (delete only with clean --records)
  points/pre/, post/, <combined group>/   the same, for the stages
  logs/<point>/         cards/ config/ context.toml commands.sh <tag>.log (each tool's digest)   <tag>.full.log with keep logs
                        history/<n>/: earlier attempts' logs and cards
                        while it runs, and kept when it fails or with keep work: FIFOs, scratch files, shards
  logs/plot/            the plot stage's failures
  config/               the errand file and cards it ran with
  cluster/<stamp>/      heimdall cluster's submissions

results/<A>/<E>/<R>/
  plot.toml             its plot document, what every drawing reads
  report.toml           its report's recipe
  points/<point>/       the products only (a link into library/ for a library point)
  pre/, post/           the stages' products
  plots/<set>/<backend>/[<cell>/][<figure>/]<object>.<fmt>   pages, with index.html; plots/index.html links every set
  plots/<set>/<backend>/sheets/<figure>.{pdf,png}
  statistics/<set>/     statistics.csv, bars/, summary.pdf, summary.html, figures/
results/<A>/<E>/compare/<figure>/<backend>/   a compare figure's pages

reports/<A>/<E>/<R>/    figures/ stats/ tools/ report.tex report.pdf index.html

.cache/<A>/plots/<E>/<R>/   the drawing's working files: the merged sweep, page documents, derived YODAs
.cache/<A>/<tool>/<key>/    prepare caches (slow to rebuild: an integration)
.cache/<A>/datasets/        reference data converted for Paint
.cache/<A>/reproduce/<identity>/   heimdall reproduce's run
build/                  compiled modules and Rivet plugins
```

## The points library

With `[errand] library = true` the generation points of an Assignment are pooled: a point whose physics another Run or Errand of it already made is not run again, and its `points/<name>` is a link into the entry (`"only"`: the run makes the entries alone, with no manifest, combine, post or plot, and removes its links at its end). Nothing in an identity or a seed changes. [Identity](../internals/identity.md) says what the key is.

```bash
heimdall library list [A]           # entries: tags, events, seed, complete or not, who made each, who links it now
heimdall library verify [A]         # each entry complete for its key, products there, links resolve; fixes nothing, exit 1 on a problem
heimdall library prune [A] [--duplicates] --yes   # the entries no Run links; without --yes it only says
heimdall library adopt <A>/<E>/<R> --yes          # file a Run's finished points into the library, and link them back
```

`--rerun` reruns a library point in its entry, replacing it for every Run that links it, and says which. `heimdall clean` takes a Run's link away and never an entry. `prune` and `adopt` refuse while a job of the work dir goes. `adopt` judges a point by its recorded parts: a point whose key is already in the library is linked to that entry and its own folders stay beside the link as `<name>.adopted-duplicate`; an unfinished entry of its key stops it.

## What a run keeps

Besides `records/` and `results/`, a finished point keeps its `cards/`, `config/`, `context.toml`, `commands.sh` (each tool's command line, folder and environment), each tool's digest and `history/`, and prepare caches. A failed point keeps everything. Deleting `logs/<point>/` reruns nothing, but loses those.

More with a `keep` word: `logs` (every tool's whole output), `journal` (`status.jsonl`), `work` (a finished point's whole working folder), `cache` (card checks, converted data, the plot stage's working files). The words come from `heimdall run --keep` (`--logs` and `--journal` are two of them), the work dir's `heimdall.toml [run] keep` and the machine's `machine.toml [run] keep`, together.

`[run] log` in those files sets a digest's `head` and `tail`, the history's `digests` and `full`, and a detached worker's `worker_every`.
