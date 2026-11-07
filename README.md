# Heimdall

A framework for Monte Carlo studies in high-energy physics, and the home of the software stack it runs on. **Tools are processes, chained by a TOML:** Pythia, Herwig, Sherpa, Whizard and MadGraph, Rivet, Delphes, your own programs, and the pages drawn with ROOT.

This folder is `$HEIMDALL`: what is authored. What it builds goes in Himinbjorg, `~/Himinbjorg`. Your studies live in **work dirs**, as many as you like.

## From nothing to a drawn page

```bash
git clone <Heimdall's URL> ~/Github/Heimdall && cd ~/Github/Heimdall
python3 recipes/build_stack.py packages=@primary   # a conda base, then the stack from source (hours); @primary-conda: minutes
source gjallarhorn.sh                              # the environment (later: gjallarhorn)
heimdall build --framework                         # Heimdall's apps
heimdall doctor                                    # what the stack can do, checked
heimdall setup ~/Study --example jets              # a work dir, with the demo assignment
cd ~/Study && heimdall build                       # its Rivet plugin and module programs
heimdall run Demo/jets single                      # one point: Pythia → Rivet → ROOT, then the pages
```

The pages are in `results/Demo/jets/<R>/plots/totality/root/index.html`. On macOS or in an image: [platforms](docs/stable/setup/platforms.md), [images](docs/stable/setup/images.md).

## Where next

The docs: [docs/README.md](docs/README.md). `heimdall help` lists the commands, `heimdall explain <key>` says what any setting does, `heimdall docs` opens it all as one searchable page. Agents: [AGENTS.md](AGENTS.md).
