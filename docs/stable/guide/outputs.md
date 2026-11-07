---
id: outputs
summary: what a run writes and where: records, results, reports, cache; what is kept; what may be deleted
code: framework/runner/tools.py, framework/runner/paths.py
---

# Outputs

Each tree has one purpose. **`records/`** is what a run needs while it runs or is launched, and what traces it back. **`results/`** is what matters afterwards. **`.cache/`** is rebuilt on demand, and `rm -rf .cache` is always safe. A run writes nothing else, and nothing in Heimdall.

`<E>` is the errand's name; `<R>` is `NN_<name>`, its serial and its configuration's folder ([paths](paths.md)). `<point>` is the swept tags joined by `_`, or `point`.

```
records/<A>/<E>/<R>/
  points.json           every point's values, products, identity, state
  run.jsonl             the run's own log, every run's        status.jsonl with keep journal
  tag                   the folder's tag, when it has one
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
  points/<point>/       the products only
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

## What a run keeps

Besides `records/` and `results/`, a finished point keeps its `cards/`, `config/`, `context.toml`, `commands.sh` (each tool's command line, folder and environment), each tool's digest and `history/`, and prepare caches. A failed point keeps everything. Deleting `logs/<point>/` reruns nothing, but loses those.

More with a `keep` word: `logs` (every tool's whole output), `journal` (`status.jsonl`), `work` (a finished point's whole working folder), `cache` (card checks, converted data, the plot stage's working files). The words come from `heimdall run --keep` (`--logs` and `--journal` are two of them), the work dir's `heimdall.toml [run] keep` and the machine's `machine.toml [run] keep`, together.

`[run] log` in those files sets a digest's `head` and `tail`, the history's `digests` and `full`, and a detached worker's `worker_every`.
