---
id: decisions-stack
summary: why the stack is built as it is: recipes, toolkits, the conda base, Himinbjorg, images, the cluster
---

# Decisions: the stack

The full account of each is at tag `docs/pre-rebuild`, in `docs/07_Record.md`.

- **V78** One registry of the software stack, `env/stack.toml`: each library's flags and version.
- **V107** `heimdall setup` makes a work dir from a template: a template edit, never a code change.
- **V109** The stack's recipes live in `recipes/`. Location now per V122.
- **V110** Toolkits: preset sets of tools for a kind of work, and your own.
- **V113** Portable where it was Linux-only: the watch socket, Paint's `base.toml`.
- **V114** `heimdall cluster`: a run as Slurm jobs, with no executor of its own, since a job is an ordinary `heimdall run`.
- **V116** Downloads are verified: mirrors, resuming, retries, checksums.
- **V117** A clean build environment, a preflight, explicit optional dependencies.
- **V118** Platform fixes as recipe lines; stamps that know their recipe.
- **V119** `heimdall doctor`: what a machine can do, checked by each recipe's `verify`.
- **V120** A support matrix: each machine's row from `doctor --record`.
- **V121** After an OS upgrade: what broke, and its rebuild, from recorded links.
- **V123** Toolkits as files, one package registry in `standard.toml`.
- **V124** The shell: bash only, one stack at a time, and a quit that undoes everything.
- **V135** The first run: one path per platform, from the clone to a drawn page.
- **V139** What porting a real study found: `setup` in a repository whose `.gitignore` ignores a work dir's file.
- **V140** A conda base is the default for a new Himinbjorg: no root needed.
- **V141** Ready-made toolkits from conda-forge.
- **V142** The program is `heimdall`; the loader is `gjallarhorn.sh`.
- **V143** `heimdall recognise`, `workdirs.toml`, `gjallarhorn [title]`.
- **V144** `bifrost`: adding packages to the environment.
- **V145** The machine's own recipes; flags gated by version.
- **V147** `bifrost -c` and `-b`: a tool ready-made or built, and what a switch costs.
- **V150** Apptainer images: the runtime is the system's, never Himinbjorg's.
- **V155** MadGraph pointed at the whole stack.
- **V189** NLO in Sherpa: one-loop providers, `@loops`, Amegic's compile in the prepare step.
- **V192** A build's compilers follow what the machine has free.
- **V193** Every recipe built here carries its archive's sha256.
- **V194** Small defects: a doubly defined constant, a dead branch.
