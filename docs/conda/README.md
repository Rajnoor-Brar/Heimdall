# A conda base for the machine root

**The question (the user, 2026-10-14):** what are the prospects and the practicality of conda for
a proper environment in the machine root, instead of today's Python venv? The user then sharpened it:
the tools can still be built from source. What conda adds is that its environments hold more than
Python: the compilers, utilities and libraries now taken from apt (or Homebrew).

This set answers it and designs that model.

**Status (2026-10-14): implemented, and the default for a new machine root** (record V140, V141). The
user ordered it the same day: the base is how a machine root is built, the tools are still built from
source inside it, separate `@…-conda` toolkits take conda-forge's ready-made packages, and existing
stacks are not converted (a root with a `venv/` and no `base/` stays `base = "system"`). Phase 2 was
done directly; phase 1's hand build was replaced by the verification of the implementation in two
scratch roots; phase 3 (the slow suite on a base stack, physics against today's stack, the Mac) is
pending. [03_Plan.md](03_Plan.md)'s Log says what was found. Not done yet: the tracked
multi-platform lock ([02 §2](02_Design.md#2-the-package-list-and-its-lock); each machine solves its
own `base/pixi.lock`), and a bootstrap for clusters whose Python is older than 3.11.

**The user's decisions (2026-10-14):**
- **Design first:** this set, before any install.
- **pixi** manages the environment, not Miniconda, Miniforge or micromamba.
- **conda-forge only.** The hep-forge channel is not used for now.
- **The HEP tools stay built from source** by Heimdall's recipes. A ready-made conda-forge package is
  at most a shortcut, chosen per package.

## The model in one picture

```
 today                                     with a base
 ─────                                     ───────────
 OS (apt / Homebrew)                       OS: glibc, kernel, GPU driver, TeX
   compilers, gsl, libzip, libxml2,        base/  (pixi, conda-forge, locked)
   boost, cmake, Python 3.x, pandoc …        compilers, build tools, gsl, libzip, libxml2,
                                             boost, X11 libs, Python + packages, pandoc …
 venv/   (Python packages only)            (venv/ retired: the base is the Python env)
 stack/  Heimdall's recipes, from source   stack/  Heimdall's recipes, from source, built inside
         against the OS's libraries                the base; linked to the base by rpath
 apps/, work dirs                          apps/, work dirs: unchanged
```

Only the bottom layer changes owner. The OS keeps glibc, the kernel and the drivers. Everything the
stack links besides those comes from one locked, versioned list that Heimdall holds.

## Contents

| | |
|---|---|
| [01_Assessment.md](01_Assessment.md) | today's layers and what broke; what conda-forge carries for the base (entry by entry against the apt list and the Brewfile) and for the HEP tools; hep-forge; Miniconda and the alternatives; gains, costs, unknowns |
| [02_Design.md](02_Design.md) | the base in the machine root: layout, the package list and its lock, building inside the base, the stack's identity, the runtime, ready-made packages, platforms, what stays outside, this machine |
| [03_Plan.md](03_Plan.md) | three phases of three steps: the base by hand in a scratch machine root, the integration in Heimdall, the trial and the adopt-or-not decision |

The facts about conda-forge come from anaconda.org's package API, read on 2026-10-14. Claims about
Heimdall cite `file:line` at `864c0f4`.
