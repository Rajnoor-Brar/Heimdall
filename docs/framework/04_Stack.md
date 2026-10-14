# 04 — P1: The stack

**Goal.** Build the software stack into the machine root, `~/Himinbjorg` (`$HEP_MACHINE`, outside
git): **`@primary`**, every package the lab PC had (`packages=all`: core and extra) plus MadAnalysis5.
The places (V109, V122) are:
- `forge/downloads/` and `forge/src/` for the downloads and their unpacked sources;
- `forge/build/` and `forge/logs/` for the build trees and logs;
- `base/` for the conda base: the compilers, the libraries the stack links, and the Python environment
  with its `heimdall.pth` (pixi makes it from conda-forge; `forge/pixi/` holds pixi itself);
- `stack/` for the installs and their stamps (installs only).

`setup.sh` cannot be sourced before the root exists, so this phase's shell sets
`export HEP_MACHINE=~/Himinbjorg` (the default) for the rows below.

The steps:
- **S1:** the base (no sudo).
- **S2:** the build, in the background, for hours.
- **S3:** the result checked against the lab PC's numbers.

**Reads:**
- [recipes/README.md](../../recipes/README.md): §1 (resuming, cores, the base), §3 (why each flag), §4
  (the base, or the system's packages), §6 (toolkits);
- the annex `targets/<annex>.md`: the allowed adjustments (and its system packages, with `base=system`).

**Writes:** `$HEP_MACHINE/{forge,base,stack}`, `$HEP_MACHINE/machine.sh` (when the annex has
`setup_extra` lines), `$HEP/.setup/`.

**Gates:**
- downloads: pixi and the base's packages (S1, once), the sources (S2, once);
- a package that fails twice; MadAnalysis5 failing at all (its recipe is `status = "new"`: not yet
  proven by a build).

---

## S1: the base

**Preconditions:**
- P0 is verified.
- `git -C $HEP status --porcelain` is empty.

**Tasks:**

1. **The dry run,** which also checks the recipes on this machine:
   ```bash
   cd $HEP && python3 recipes/build_stack.py --dry-run packages=@primary 2>/dev/null > .setup/build.sh
   ```
2. **The gate:** the base's downloads, asked once: pixi (about 34 MB, from github.com/prefix-dev/pixi,
   checked against `recipes/base.toml`'s sha256) and the base's conda-forge packages (about 1 GB of
   downloads, 2.3 GB installed: the compilers, the libraries, Python and its packages).
3. **The base**, alone, before the long build:
   ```bash
   cd $HEP && python3 recipes/build_stack.py --base packages=@primary > .setup/base.log 2>&1
   ```
   It needs no sudo, and nothing outside the machine root changes (pixi's settings and cache are in
   `forge/`). On the user's word, or where conda-forge cannot be reached, `base=system` is the way
   before: the annex's apt list (`recipes/settings.toml`'s `apt_packages`, through the annex's
   allowed adjustments, 02 §7), installed with sudo as a gate, then `base=system system=false` in S2.

**Verification:**

| # | Command | Expected |
|---|---|---|
| R1 | `cd $HEP && bash -n .setup/build.sh && echo ok` | `ok` |
| R2 | `grep -c '^# == ' $HEP/.setup/build.sh` | `20` (python lhapdf hepmc3 fastjet fjcontrib root hdf5 yoda rivet pythia8 thepeg herwig delphes pdfsets sherpa madgraph whizard onnxruntime geant4 madanalysis5) |
| R3 | `grep -c "$HEP_MACHINE/forge/\|$HEP_MACHINE/stack/" $HEP/.setup/build.sh` | ≥ `100` (131 in a scratch root, 2026-10-14: every package's paths in the machine root) |
| R4 | `grep -c "recipes/patches/fastjet" $HEP/.setup/build.sh` | `1` (the SISCone patch, L29) |
| R5 | `ls $HEP_MACHINE/base/.pixi/envs/default/conda-meta/*.json \| wc -l` | about `206` (a scratch root's, 2026-10-14) |
| R6 | `source $HEP_MACHINE/base/activate.sh && $CXX --version \| head -1` | conda-forge's GCC `15.x` |
| R7 | `source $HEP_MACHINE/base/activate.sh && echo \| $CXX -x c++ -E -v - 2>&1 \| grep -c '^ /usr/include'` | `0`: the base's compiler never reads the OS's headers |

**On failure:**
- R1–R4: the recipes do not plan here. Collect the dry run's stderr; this is a gate (the recipes
  are Heimdall's code).
- R5–R7: the base did not install. Collect `$HEP_MACHINE/forge/logs/base.log` (pixi's solve and
  download); this is a gate.

---

## S2: the build (background)

**Preconditions:** S1 `done`.

**Tasks:**

1. **Kept tarballs** (01 §8, optional). Copy them from `$HEP/.setup/kept/downloads/` into `$HEP_MACHINE/forge/downloads/`
   under the names `build_stack.py` looks for, `<package>-<release><ending>`. An archive already
   there is used as it is, which saves about 555 MB of downloads:

   | Kept (the lab PC's name) | As |
   |---|---|
   | `LHAPDF-6.5.6.tar.gz` | `lhapdf-6.5.6.tar.gz` |
   | `HepMC3-3.3.1.tar.gz` | `hepmc3-3.3.1.tar.gz` |
   | `fastjet-3.5.0.tar.gz`, `fjcontrib-1.104.tar.gz` | the same |
   | `root_v6.40.04.source.tar.gz` | `root-6.40.04.tar.gz` |
   | `YODA-2.1.4.tar.gz` (CEDAR) | `yoda-2.1.4.tar.gz` |
   | `Rivet-4.1.4.tar.gz` (CEDAR) | `rivet-4.1.4.tar.gz` |
   | `pythia8318.tgz` | `pythia8-8318.tgz` |
   | `ThePEG-2.3.0.tar.bz2`, `Herwig-7.3.0.tar.bz2` | `thepeg-2.3.0.tar.bz2`, `herwig-7.3.0.tar.bz2` |
   | `Delphes-3.5.1.tar.gz` | `delphes-3.5.1.tar.gz` |
   | `sherpa-3.0.5.tar.gz`, `whizard-3.1.8.tar.gz`, `geant4-11.4.2.tar.gz` | the same |
   | `MG5_aMC_v3.8.1.tar.gz` | `madgraph-3.8.1.tar.gz` |
   | `onnxruntime-linux-x64-1.29.0.tgz` | `onnxruntime-1.29.0.tgz` |

   The names come from `build_stack.py`'s `tarball()`; the dry run of S1 shows each download it
   would still make.
2. **Cores.** `cores` = logical CPUs − 4. `root_cores` = RAM in GB ÷ 3, at most `cores`
   ([recipes/README.md](../../recipes/README.md) §1). On the lab PC (24 threads, 15 GB) that is 20 and 5.
   Record both in `[choices]`. The command line wins over `settings.toml`.
3. **The downloads gate.** List what is still to fetch: the archives not in `forge/downloads/` (from the dry
   run), Geant4's datasets (about 4 GB, during its build), the 21 PDF sets and MadAnalysis5's archive.
   Give the total, and ask once.
4. **Start the build** as the builder (02 §2), detached from the shell that starts it:
   ```bash
   cd $HEP && setsid nohup python3 recipes/build_stack.py packages=@primary \
       cores=<cores> root_cores=<root_cores> > .setup/stack.log 2>&1 < /dev/null &
   ```
   - `root_cores` bounds ROOT's and Rivet's compilers, each about 3 GB: more than RAM ÷ 3 of them
     exhausts the memory, and can take the machine down.
   - Watch `stack.log`: one line per package ("<name>: done in N min"), and a failure's last 30
     lines.
   - On a failure: 02 §5.2. **Resuming** is the same command; the stamps in `stack/.stamps/` skip
     what is done.
   - Expected time: ROOT alone takes 1–2 h; everything about 4–5 h at these cores.

**Verification:**

| # | Command | Expected |
|---|---|---|
| R1 | `ls $HEP_MACHINE/stack/.stamps \| grep -v '\.libs$\|^folders$' \| wc -l` | `21` (the 20 packages of S1's R2, and `cxx_std`) |
| R2 | `cat $HEP_MACHINE/stack/.stamps/cxx_std` | `17` |
| R3 | `tail -1 $HEP/.setup/stack.log` | `done: source <HEP>/setup.sh` |
| R4 | `grep -c 'failed' $HEP/.setup/stack.log` | `0` |
| R5 | `git -C $HEP status --porcelain \| wc -l` | `0` (everything the build wrote is ignored) |

**On failure:**
- A package that fails twice is a gate (02 §5.2), with its log tail (`$HEP_MACHINE/forge/logs/<pkg>.log`) and
  the probable cause. The known suspects on a newer Ubuntu are in the annex: a GCC or Python too
  new for ROOT, ThePEG, Herwig or Whizard.
- **MadAnalysis5** is a new recipe: its first failure is a gate. Everything else of `@primary` is
  the lab set, and does not need it: the user may say to go on without it (then R1 expects `20`,
  recorded as a deviation), while its recipe is fixed and folded back.

---

## S3: the stack checked

**Preconditions:** S2 `done`.

Every row runs in a fresh shell after `source $HEP/setup.sh`. The expected values are the lab PC's
of 2026-10-10 (`hep status --stack`, `lhapdf list --installed`).

**Verification:**

| # | Command | Expected |
|---|---|---|
| R1 | `root-config --version` | `6.40.04` |
| R2 | `pythia8-config --version` | `8.318` |
| R3 | `rivet --version` | `rivet v4.1.4` |
| R4 | `yoda-config --version` | `2.1.4` |
| R5 | `HepMC3-config --version` | `3.03.01` |
| R6 | `fastjet-config --version` | `3.5.0` |
| R7 | `lhapdf-config --version` | `6.5.6` |
| R8 | `geant4-config --version` | `11.4.2` |
| R9 | `Herwig --version \| head -1` | contains `7.3.0` |
| R10 | `Sherpa-config --version` | `3.0.5` |
| R11 | `whizard --version \| head -1` | contains `3.1.8` |
| R12 | `grep -i version $HEP_INSTALL/madgraph/VERSION` | contains `3.8.1` |
| R13 | `test -f $HEP_INSTALL/onnxruntime/lib/libonnxruntime.so && test -x $HEP_INSTALL/delphes/bin/DelphesHepMC3 && echo ok` | `ok` |
| R14 | `test -x $HEP_INSTALL/madanalysis5/bin/ma5 && echo ok` | `ok` |
| R15 | `lhapdf list --installed \| wc -l` | `21` |
| R16 | `lhapdf list --installed \| tr '\n' ' '` | `CT10 CT14lo CT14nlo CT18NLO CT18NNLO MSHT20nlo_as118 MSTW2008lo68cl MSTW2008lo68cl_nf3 MSTW2008lo68cl_nf4 MSTW2008lo68cl_nf4as5 MSTW2008lo90cl MSTW2008lo90cl_nf3 MSTW2008lo90cl_nf4 MSTW2008lo90cl_nf4as5 NNPDF23_lo_as_0130_qed NNPDF23_nlo_as_0119_qed NNPDF40_nlo_as_01180 PDF4LHC21_40 PDF4LHC21_40_pdfas cteq6l1 nNNPDF30_nlo_as_0118_A208_Z82` |
| R17 | `grep -rl thread_local $HEP_INSTALL/fastjet/include/siscone \| wc -l` | `1` (the SISCone patch, L29) |
| R18 | `python -c "import ROOT, pythia8, yoda, rivet, lhapdf, pyHepMC3, uproot, tomli_w, yaml; print('ok')"` | `ok` |
| R19 | `cat $(python -c "import site; print(site.getsitepackages()[0])")/heimdall.pth` | `<HEP>/framework`, expanded |
| R20 | `which python; echo $HEP_BASE; echo $HEP_INSTALL` | `<machine root>/base/.pixi/envs/default/bin/python`, `<machine root>/base/.pixi/envs/default`, `<machine root>/stack` |
| R21 | `hep where` | `hep=<HEP> <revision>` and `work=-`, and no warning about `heimdall.pth` |
| R22 | `du -sh $HEP_MACHINE/stack/ \| cut -f1` | about `6.0G` (the lab set's; MadAnalysis5 adds little) |
| R23 | `pkg-config --modversion tomlplusplus libzstd zlib` | the base's: `3.4.0 1.5.7 1.3.2` (2026-10-14). Recorded, not compared |
| R24 | `ldd $HEP_INSTALL/rivet/lib/libRivet.so \| grep '=> /usr/lib\|=> /lib' \| grep -v 'libc\.\|libm\.\|libdl\.\|libpthread\.\|librt\.\|ld-linux'` | nothing: every library but glibc's from the base or the stack |

**On failure:**
- R17 = 0: the patch was not applied, and InprocJets' `rivet_threads > 1` will refuse. Collect
  `$HEP_MACHINE/forge/logs/fastjet.log`.
- R18: name the module that fails, and check its install's Python directory against `hep_env.sh`'s
  `PYTHONPATH` lines.
- R19 or R21's warning: `recipes/pth.py` did not run (the `python` package's last step); run it by
  hand, `$HEP_VENV/bin/python recipes/pth.py $HEP`, and record a deviation.
