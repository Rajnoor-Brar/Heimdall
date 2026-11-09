---
id: sweeps
summary: recipes for varying things: grids, zips, fixed values, native keys, analysis options, several configurations, listed points
code: framework/runner/sweep.py, framework/runner/quantities.py, framework/runner/config.py, framework/schema/quantities.toml
---

# Sweeps and points

No `vary` means one point, with every active quantity at its `fixed` point. Every key: [quantities](../../reference/settings/errand.md).

## A sweep, a grid, a zip

```toml
[cfgs.pdf]
vary = ["pdf"]                         # a point per PDF: a page per histogram, a curve per PDF

[cfgs.energy_pdf]
vary        = ["energies", "pdf"]      # 4 × 4 = 16 points
plot_points = ["energies"]             # a page folder per energy; the PDFs are the curves

[cfgs.zipped]
vary = ["energies", ["pdf", "alphas"]] # pdf and alphas zipped: point i with point i
```

`plot_points` names the quantities that make pages; every other varied quantity makes curves. An inner list is one axis whose quantities have equal point counts. A quantity's `exclude = [N, …]` leaves points out, 1-based.

## Quantities that move together

Better written as one, with fields: a row per point, a value per field.

```toml
[quantities.collision]                 # vary = ["collision"]: beams and nucleus together
fields = { energies = "energies", nucleus = { pythia = "PDF:nPDFBeamA" } }
fixed  = "p"
points = [
  { tag = "p",  energies = [130, 9], nucleus = 2212,       label = "$e$p" },
  { tag = "Au", energies = [100, 9], nucleus = 1000791970, label = "$e$Au" },
]
```

Or list combinations by hand: `vary = [{ points = [{ pdf = "a", energies = "x" }, …] }]`. A row may leave a quantity out, and the card's own value then stands.

## Fixed values

```toml
[cfgs.mpi]
vary  = ["pt0ref"]
fixed = { energies = "18x275" }        # over the quantity's own fixed, for this configuration
```

A fixed point is a tag, an exact value, or `"#N"`. `--set cfgs.mpi.fixed.energies=10x100` changes it for one job.

## Where a quantity goes

The vocabulary (`framework/schema/quantities.toml`, and each tool's `quantities.toml`) already maps `energies`, `pdf`, `sqrts`, `beams`, `events` and more. Anything else names its target with `to`:

```toml
[quantities.pt0ref]
to     = { pythia = "MultipartonInteractions:pT0Ref" }   # a native key, per tool table or tool
points = [
  { tag = "pt30", value = 3.0, label = '$p_{T0}^{\mathrm{ref}}$ = 3.0 GeV' },
  { tag = "pt32", value = 3.2, label = '$p_{T0}^{\mathrm{ref}}$ = 3.2 GeV' },
]

[quantities.radius]
to     = { "rivet/photo_eic" = "R" }   # an analysis option, as its .info declares it
points = [{ tag = "r04", value = 0.4 }, { tag = "r07", value = 0.7 }]

[quantities.replica]
to     = { "pythia/seed" = true }      # a replica: the same physics, its own seed
points = [{ tag = "s1", value = 1 }, { tag = "s2", value = 2 }]
```

An entry with a `/` or `true` makes the entries the only consumers. An override equal to the base card's own value is written, but does not change the identity.

An analysis option its `.info` does not declare is refused: Rivet would ignore it and give identical curves. Each variant is a curve on the object's page, labelled `… [R=0.4]`.

**Each value is its own generation:** a three-point option vary runs Pythia three times. To avoid that, keep the events once as a file, with the generator in a group of its own, and analyse them in another configuration.

## Several configurations

```toml
[errand]
sweep_runs = ["pdf", "energies"]       # heimdall run jets: these, in order. true: every one, in file order
```

Each makes an ordinary Run. All are checked before the first starts, so a typo in the last costs nothing. With a terminal or `--detach` they are a queue: one worker a Run, the next starting when the one before ends, each with its own `heimdall runs` entry, log and `[N]`. A failed Run lets the next start; a stopped one holds the rest until `heimdall runs --dispatch`; `heimdall watch` follows each in turn. Without a terminal they run one after another in one process. A shell loop can do none of that. `heimdall run jets pdf` still runs only `pdf`.

A configuration may also choose a tool by a quantity, `chain = [["@generator", "rivet"]]`: [chains](chains.md).
