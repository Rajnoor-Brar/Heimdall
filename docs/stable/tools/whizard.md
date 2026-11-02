---
id: tools-whizard
summary: the whizard tool: SINDARIN point cards, beams by name, what the plan owns, its limits
code: framework/tools/whizard/tool.toml, framework/tools/whizard/render.py
---

# `whizard`

```toml
[tools.whizard]
card   = "ep.sin"               # exactly one base card
output = "events.hepmc"
```

- **Card** (`render.py`): SINDARIN is a script, so the point card comes first and includes the base last: the plan's assignments, `seed`, `sample_format = hepmc`, `$sample`, then `include("<base>")`.
- **Beams are names:** PDG codes become the SM model's names. The base card states its structure-function chain in a comment, `# heimdall: beam_structure = pdf_builtin, epa`.
- **The plan owns** `seed`, `n_events`, `sqrts`, `beams`, `beams_momentum`, `$sample`, `sample_format`: a base assigning one is refused, as it would run after the plan's value.
- **Prepare**, the integration: `whizard <prepare card>`. Generation then runs in the cache entry (`[command] cwd`), where Whizard finds it.
- **Consumes** `energies`, `beams`, `events`.
- **σ:** none in its events, so Rivet has none; the integration log has it.
- **Limits:** no photon structure function, so direct photoproduction only. Its EPA record has no scattered lepton, so a Rivet analysis using `DISKinematics` cannot run on it.

- **L13** SINDARIN is a script: the point card goes first, then include the base. `--execute` runs before the card. The integration card strips `n_events`, `$sample` and `sample_format`.
