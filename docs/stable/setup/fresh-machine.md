---
id: fresh-machine
summary: from a clone to a working Heimdall on a new machine: what you need, the build, a first work dir, the checks
code: recipes/build_stack.py, gjallarhorn.sh, framework/runner/setup.py
---

# A fresh machine

## What you need

`git`, `curl`, and `python3` 3.11 or newer (older with `tomli`). No sudo and no compilers: the conda base brings them. About 60 GB free for a whole stack, and hours of build time (ROOT alone takes 1–2 h), or minutes with a ready-made toolkit. pdflatex for sheet figures and reports stays the OS's: on Ubuntu, `texlive-latex-recommended` and `-extra`.

Per platform: [platforms](platforms.md). In an image: [images](images.md). On a cluster: [cluster](cluster.md).

## Build

```bash
git clone <Heimdall's URL> ~/Github/Heimdall && cd ~/Github/Heimdall
python3 recipes/build_stack.py --list                 # each package: release, state, what this run builds
python3 recipes/build_stack.py packages=@primary      # a conda base, then the stack from source (hours)
source gjallarhorn.sh                                 # the environment, in bash (any shell: ./launch.sh)
heimdall build --framework                            # Heimdall's apps, into the machine root's apps/
heimdall doctor                                       # what every package can do, checked
```

`packages=@primary-conda` takes the tools ready-made instead, in minutes. Which toolkit: [toolkits](toolkits.md). What the build does and how it resumes: [stack](stack.md). Start a long build detached (`setsid nohup … < /dev/null &`), or a session's end kills it.

Everything goes in the machine root, `~/Himinbjorg` (`$HEIMDALL_MACHINE`, or `machine=`), outside git.

## A first work dir

```bash
heimdall setup ~/Github/My-Study --assignment Jets --git
gjallarhorn My-Study && heimdall build
heimdall run Jets/jets --plan
```

Then: [first-run](../start/first-run.md). A folder must be empty, a work dir to complete, or a fresh git repository (only `.git/` and a hosting site's README, LICENSE, `.gitignore`); any other needs `--adopt`. A repository's own `README.md` and `CLAUDE.md` are kept (Heimdall's guide goes in `HEIMDALL.md`), its `.gitignore` gains a marked block, and `--git` commits only what was added (`--git=new` in a nested repository). `--example jets` adds a working assignment to run first. It fetches what `datasets.toml` lists. `--refresh` shows, as a diff, each framework-written file (the Makefile, `.vscode/`, Heimdall's README.md and CLAUDE.md) that differs from today's template, and writes it (asked, unless `--yes`); the user's files are never touched. A template edit changes what every new work dir gets.

Verify: [verify](verify.md).
