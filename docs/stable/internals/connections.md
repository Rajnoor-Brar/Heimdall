---
id: connections
summary: how tools connect: FIFOs, files, products, the rules checked at plan time, the context file, sharding
code: framework/runner/tools.py
---

# Connections

A tool table names what it reads and writes; the runner infers FIFO or file from the chain, and never guesses a connection.

| Interface | Made by | Lives in | Connects |
|---|---|---|---|
| FIFO | the runner, fresh per attempt, removed when the point ends | the point's working folder | a writer and **one** reader in the same group |
| file | the runner (empty), then its writer; kept | the point's working folder | a writer and readers in later groups |
| product | its tool, as `*.partial.*`, renamed after the checks | the point's results | later groups, the plot stage, post tools |
| pre product | a pre tool | `…/<R>/pre/` | every point |
| every point's product | the points | their results | a post tool |

## The rules (C6)

| Rule | Why |
|---|---|
| A FIFO connects tools in one group only | it needs both ends open: a reader in a later group leaves the writer blocked for ever (L8) |
| Between groups, a regular file | the earlier group has finished, so the file is complete |
| A FIFO has one reader; fan-out is a list-valued output | two readers would split the stream |
| A sharded tool reads from a producer that can deal | below |
| No FIFO into a tool not `streamable` | Delphes skips zero-length input, which a FIFO always is (L11) |
| Every input is produced earlier or in the same group, or exists | |
| Every output has one writer | two writers race |

**L8** Opening a FIFO blocks until both ends are open. A dead writer leaves the reader blocked for ever, and there is no SIGPIPE.

## The context file

Connections move data; the context file moves configuration. Each point's `context.toml` lists every tool's card and config: the chain's, and those of tables in `generate_cards`, which are configured without being run. Every tool gets it as `$HEIMDALL_CONTEXT`. That is how an **integrated program**, one process running Pythia and Rivet, gets the chain's card and seeds.

## Sharding

A Rivet process uses one core, and in a Pythia → Rivet chain it sets the pace whatever Pythia's threads. `shards = K` is rewritten per point, before anything else is planned (`tools._shard`):

```
[["pythia", "rivet"], "yd2rt"]         with [tools.rivet] shards = 3
  → [["pythia", "rivet.1", "rivet.2", "rivet.3"], ["rivet.merge"], ["yd2rt"]]
     pythia writes  events.s1.hepmc+events.s2.hepmc+events.s3.hepmc   (a deal group: one each)
     rivet.<i>      reads events.s<i>.hepmc, writes records/…/logs/<point>/shards/jets.s<i>.yoda
     rivet.merge    rivet-merge -e the three → results/…/jets.yoda
```

`_outputs_argument` renders the `+` group, a `<tag>.merge` step of the folder's `[shard] merge` tool is inserted, and `_retarget` points quantities at every copy. All rules above then apply. Each shard is count-checked against its share of the sidecar (`written_per_output`); the generator's seeds follow its cards, not its argv, so events match the unsharded run; shard products are technical, not in `points.json`, not drawn.

**L28** Each output must end on the latest σ. A shard's Rivet, like any CLI Rivet, normalises to the σ of the last event it reads, so with events dealt each shard's last event must carry the final σ.
