---
id: tools-madgraph
summary: the madgraph tool: proc card, launch script, the cached process directory, showering its LHE
code: framework/tools/madgraph/tool.toml, framework/tools/madgraph/render.py
---

# `madgraph`

```toml
[cfgs.single]
chain = ["madgraph", ["shower", "rivet"], "yd2rt"]   # an LHE file, then a FIFO from the shower

[tools.madgraph]
card   = "dis_ep.proc_card.mg5"   # the proc card: processes only, no output or launch
output = "unweighted.lhe"
keep   = false

[tools.shower]
uses   = "pythia"
card   = "shower_lhe.cmnd"        # sets Beams:frameType = 4; the LHEF line is the footer
input  = "madgraph"
output = "events.hepmc"
```

- **Prepare**, keyed on the proc card only (`key = "base"`): the process directory, built once.
- **Card**, a launch script: `set automatic_html_opening False`; `launch <cache>/process -n r<seed>`; shower, detector and analysis off; `set iseed <seed>`; a `set` per value. Beams become `set lpp1/lpp2`, from `[render.lpp]`.
- **Runs** the launch, then unpacks the LHE to the output.
- **Consumes** `energies` (beam 1 is the proc card's first incoming particle), `beams`, `events`.
- **Context file:** `card`; the product `"madgraph:process"`, prepared on demand.

- **L14** A launch script, `lpp_for`, and four steps. The shower runs as Pythia with `Beams:frameType = 4` and `Beams:LHEF`. It opens a browser from a batch stage unless told otherwise.
