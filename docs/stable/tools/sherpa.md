---
id: tools-sherpa
summary: the sherpa tool: YAML cards, what the plan owns, the cached integration, progress, several Sherpas for one curve
code: framework/tools/sherpa/tool.toml, framework/tools/sherpa/render.py, framework/tools/sherpa/filters.toml
---

# `sherpa`

```toml
[tools.sherpa]
card   = "ep.sherpa.yaml"
output = "events.hepmc"
```

- **Card** (`render.py`): base YAMLs deep-merged in order, then each value assigned at its key path (`EPA:Q2Max`, `PDF_SET[0]`), written whole. `sqrts` becomes `BEAM_ENERGIES`. `MPI_PDF_SET` follows `PDF_SET`.
- **The plan owns** `BEAMS`, `BEAM_ENERGIES`, `RANDOM_SEED`, `EVENTS`, `EVENT_OUTPUT`, `RESULT_DIRECTORY`: a base card setting one is refused.
- **Prepare**, the integration, cached by the card without `EVENTS`: `Sherpa -f <card> -e 0 "RESULT_DIRECTORY: <cache>/Results" "EVENT_OUTPUT: None"`. Sherpa exits 0 even when it set up no process; the step then fails, quoting Sherpa's reason. σ ± err shows as it goes.
- **Runs** `Sherpa -f <card> "RESULT_DIRECTORY: <cache>/Results"`.
- **Progress:** display arguments `BATCH_MODE: 23` and `EVENT_DISPLAY_INTERVAL` make it print a line per thousandth of the run. They are in no identity. A card's own `BATCH_MODE` is not used.
- **Consumes** `energies`, `beams`, `sqrts`, `pdf` (checked), `events`.
- **Context file:** `card`; the product `"sherpa:results"`, prepared on demand.
- Sherpa writes a YODA variation per extra weight; the plot stage draws the nominal. With `MI_HANDLER: Amisic`, ep photoproduction made 0 events in 768 s, so the committed card has MPI off.

## Several Sherpas for one curve

A point is one Sherpa process. To spread a long point over K cores, vary a seed replica and merge it back. Every replica shares the cached integration.

```toml
[quantities.replica]
to     = { "sherpa/seed" = true }
points = [{ tag = "s1", value = 1 }, { tag = "s2", value = 2 }, { tag = "s3", value = 3 }, { tag = "s4", value = 4 }]

[errand]
events      = 2_500_000            # each: 10M in all
parallelism = 4

[cfgs.generator_pdf]
vary    = ["generator", "pdf", "replica"]
combine = ["replica"]
```

## What running it taught us

- **L12** Sherpa prepends `./` to the output name, so use a relative FIFO name. Prepare with `RESULT_DIRECTORY` and `EVENT_OUTPUT: None`, or it opens the FIFO at initialisation and waits for a reader only generation starts. The YAML is deep-merged and written whole.
- **L31** Its event counter (3.0.5) prints `Event <n> ( <elapsed> elapsed / <left> left ) -> ETA: <date>`, then `XS = <σ> pb +- ( <err> pb = <%> % )`, at `BATCH_MODE`'s interval.
