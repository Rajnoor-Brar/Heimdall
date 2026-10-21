# Current plan

**Task F is done** (V151–V154, 2026-10-15; its plan below). Open: audit 4 (below). The decisions are in docs/07_Record.md (V1–V154); finished task logs
are in [archive.md](archive.md) (the latest: tasks A–E of 2026-10-14, V140–V150); ideas not built are
in [intent.md](intent.md).

## Task F: generators and tool setups compared in one configuration (done 2026-10-15, V151–V154)

Built in the order F3, F4, F1, F2, F5 (`3bdd4ea`, `292546d`, `8d75401`, `31f24be`, and the docs commit). As planned,
with these differences: the record rows are numbered in building order; a `@q` alone in a one-member group
(`["@q"]`) is a chain entry too (the parser cannot tell the two apart); a listed group's page key is a tuple
of its paged members' indices; the slow test runs listed points in a work dir of its own (a new fixture config
would need a v2 reference text, which the rules do not allow adding).

**The user's questions (2026-10-14):** "How about being able to sweep across tools configurations (such
as for comparative studies of event generators); or we just execute separate runs overlay run results."
Then: "make plan; also for three, make value = ["A", ["B","C"]] turn ["@var", "D"] into ["A", ["B","C"],
"D"] (as far as the final nesting is valid/permitted/makes sense, else throw an error). Also look into
coupling of vars: ["@var1", "@var2"] and points are [A,E] [B,E] [B,G] [C,F]", "simultaneous setting of
multiple vars for a point". Nothing is built before the user's order.

**What exists (read from the code, and dry-run in a scratch copy of the fixture work dir):**
- A quantity chooses a tool (V19): `chain = [["@generator", "spectra"], "yd2rt"]`, the values tool
  tables (`Generators/generators`: Pythia, Herwig, Sherpa; one page per object, a curve per generator).
  Two tables of one tool (`[tools.monash]` and `[tools.a14]`, both `uses = "pythia"`, own cards) make
  `@tune` compare tool setups.
- **Coupled selectors already plan:** a compound quantity whose fields are selector names,
  `fields = { gen = "gen", ana = "ana" }` with rows AE, BE, BG, CF and `chain = [["@gen", "@ana"]]`, gave
  4 points with pythia+spectra, herwig+spectra, herwig+spectra2, sherpa+spectra2. Undocumented and
  untested.
- Across configurations: the `compare` figure (same page and curve axes; another run TOML's too);
  `heimdall overlay` for any files.

**Found limits:**
- **L-a. Chains of different shapes** cannot be alternatives: `@q` stands for one tool table, so
  MadGraph → Pythia against Sherpa alone needs two configurations and a `compare` figure.
- **L-b. A varied value one alternative does not read multiplies its points.** `vary = ["generator",
  "pt0ref"]`, pT0Ref Pythia's only: hw7_p30 and hw7_p34 (and Sherpa's two) planned and would run, the
  same physics with different seeds, curves labelled by a value they never read; no warning. C7 counts
  consumers per configuration (any alternative), not per point.
- **L-c. One `pdf` cannot feed several generators.** V40: Pythia takes `LHAPDF6:<set>` and refuses the
  bare installed name; Sherpa refuses the prefix (both refusals seen); Herwig's folder maps no `pdf`.
- **L-d. A coupled group is one plot axis:** `plot_points` naming a member selects the whole group, so
  "a page per PDF, a curve per generator that ran it" cannot be drawn from a coupled sweep.

### F1. A selector's value may be a piece of chain (the user's form)

A selector quantity's value is a tool tag (as today) or a **fragment**: a list whose items are tags or
groups (lists of tags). It is spliced where the `@q` entry stands:
- **At the chain's top level** (`["@var", "D"]`): a tag is one group (today); a fragment's items become
  the chain's entries in its place: `value = ["A", ["B", "C"]]` → `["A", ["B", "C"], "D"]`, A then B
  and C together, then D.
- **Inside a group** (`[["@var", "D"]]`): a tag is a member (today); a fragment of tags joins the group
  (`["A", "B"]` → `[["A", "B", "D"]]`, all together); a fragment holding a group is refused (groups nest
  one level: "the value 'mg5py8' of [quantities.var] puts a group inside the group of @var; write
  @var at the chain's top level").
- **`[]`** splices nothing: an alternative without a step ("with and without Delphes"). A group left
  empty is refused (as a written one is).
- **The result is checked as a written chain is**, for every value of the quantity (not only the
  points run), when the file is read: each tag a `[tools.<tag>]` table (C5), a tool at most once in a
  resolved chain (its outputs would collide: refused, naming the value), and the interfaces (F1's last
  point). A value's tags are what `heimdall clean` and the alternatives' consumer table see
  (`house.py`, `tools.py` alternatives, flattened).
- **The interfaces (FIFO or file, `[prelim]`) are inferred per resolved chain**, memoised by its groups:
  today `_inferred` unions the alternatives, which cannot work once alternatives have different groups
  (one may read an output in its own group, another later). A point's `prelim` (and so its identity)
  is its own chain's. Identities stay as they are where the alternatives share their interfaces: the
  fixture's do (checked by hand: `Generators/generators --dry-run` identities before and after, on one
  machine). The only other `@` user found is High-Energy's legacy `Comparison/generators.toml`, not a
  work dir.
- `pre` and `post` keep what they take today (`@` is resolved for the points' chain only).
- Code: `config.py` (`_groups` accepts `@` entries as now; a new `_splice(groups, quantities, tools)`
  checks every value at load), `tools.py` (`_resolve_chain` splices; `plan_point` takes the resolved
  chain's prelim; the alternatives flattened), `house.py` (tags flattened), `v3.py` (a selector's value
  may be a list: no shape refusal).

### F2. Points that set several quantities at once

Two forms, both kept:
- **A compound quantity** (exists, 04 §8.4): new values written row by row, one axis. **Documented and
  tested now with selector fields** (`fields = { gen = "gen", ana = "ana" }`, `chain = [["@gen", "@ana"]]`,
  rows AE, BE, BG, CF: the user's example, which plans today). Values may be fragments (F1).
- **New: listed combinations of quantities already declared**, in `vary`:

  ```toml
  [cfgs.compare]
  vary  = ["sqrts", { points = [
    { generator = "py8", pdf = "nn23" },
    { generator = "py8", pdf = "ct14" },
    { generator = "hw7", pdf = "ct14" },
    { generator = "sh3" },                  # Sherpa at its own card's PDF
  ] }]
  chain = [["@generator", "spectra"]]
  ```

  - Each row names one point of each quantity it sets, by tag (or `"#N"`), keeping that quantity's
    value, label and style; the group is one axis of the grid, crossed with the others (`sqrts`).
  - **A row may leave a quantity out:** that point sets nothing for it (the card's own value stands,
    no line written, no consumer needed there). This is how one alternative skips a setting only
    another reads (L-b's fix, beside F3's refusal).
  - The point's name joins the row's tags in the order the quantities first appear in the rows
    (`py8_nn23`, `sh3`). Two equal rows are refused.
  - **`plot_points` may name a member** (L-d): the pages are its tags, the curves the rows on each page
    (`plot_points = ["pdf"]`: a page per PDF, a curve per generator that ran it). A row that leaves the
    page's member out is refused there, with the hint to set it or not page by it. Naming every member,
    or `[]`, works as for a group today.
  - A quantity's `exclude` does not apply to listed rows (they are explicit); `combine` may not name a
    member (refused: replicas are a quantity of their own).
- Code: `v3.py` (the `vary` entry `{ points = [...] }`; a quantity's tags), `quantities.py` (points
  expanded from rows: a choice per row, members left out absent from `point.choice`), `config.py`
  (C3 for listed groups: each member declared, each tag one of its points, no equal rows), `plot.py`
  (page axes by a member of a listed group), `schema` (run.toml: `vary`'s table entry; `make docs`).

### F3. A varied value no tool of a point reads is refused (L-b)

- C7 stays per configuration and gains a per-point rule: every **varied** quantity of a point has a
  consumer among the tools of **that point's** resolved chain (and its `generate_cards`). Otherwise the
  plan is refused: "hw7_p30: pt0ref is varied, but no tool of this point reads it (herwig, spectra,
  yd2rt): its points would differ only by their seeds", hint: "list the combinations, leaving pt0ref
  out of herwig's rows (vary = [{ points = [...] }]), or vary it in a configuration of its own".
- A **fixed** value a point does not read stays accepted (the fixture's `beams`, which Herwig's pp
  snippet sets itself): it multiplies nothing.
- Code: `tools.py` (`plan_point`: the consumer table filtered by the point's own tags; the refusal),
  docs 04 §8.1 and §13 (C7).

### F4. One `pdf` for every generator (L-c)

- **A provider check may return the value as its tool writes it** (core, generic: `check_provider`
  returns the value `apply` writes; None keeps it). `lhapdf`'s forms:
  - `pythia`: a bare installed LHAPDF set (`CT14lo`, `CT14lo/3`) is written `LHAPDF6:CT14lo[/3]`; a
    prefixed one, one of Pythia's own set numbers or a grid file as written (V40's reason holds:
    numbers are never prefixed). Today's prefixed values write the same line: identities unchanged.
  - `bare` (Sherpa): `LHAPDF6:<set>` is written `<set>` instead of refused.
  - `set` (new, Herwig): the set's name; a `/member` is refused (Herwig's is `:Member`, in the card).
- **A scalar to a `keys` mapping is written to every key** (today it is refused as "expected N
  values"); a list still spreads over them.
- **Herwig maps `pdf`**: `pdf = { keys = ["/Herwig/Partons/HardLOPDF:PDFName",
  "/Herwig/Partons/ShowerLOPDF:PDFName", "/Herwig/Partons/MPIPDF:PDFName",
  "/Herwig/Partons/RemnantPDF:PDFName"], check = "lhapdf:set" }`: the four objects Herwig's own
  defaults set (`CT14lo` each, `share/Herwig/defaults/PDF.in`), as Pythia's `PDF:pSet` covers its hard
  process, shower and MPI. The NLO objects stay the card's. A tune is fitted with its PDF, for every
  generator alike (L24: matching PDFs is part of a fair comparison); the manual says so.
- The ledger gains a Herwig PDF row (none exists; CLAUDE.md asks to read a tool's rows first).
- Code: `quantities.py` (`check_provider`), `tools.py` (`apply`: the returned value; `keys` with a
  scalar), `framework/tools/lhapdf/provider.py`, `framework/tools/herwig/quantities.toml`,
  `framework/tools/sherpa/quantities.toml` (unchanged form), docs 05 (pythia, sherpa, herwig rows).

### F5. Docs and record

02 §5.3 rewritten as "comparing generators and tool setups" (selector values and fragments, listed
combinations, one `pdf`, the per-point refusal, when a `compare` figure is still the way); 04 §5.1
(`vary`'s listed form), §5.2 (`plot_points` by a member), §5.3 (fragments), §8.1 and §13 (C5, C7), §8.4
(selector fields); 05 (the pdf rows); 06 (config: resolved chains and their interfaces); 07, numbered in
building order: V151 (the per-point consumer rule), V152 (one `pdf` for every generator; amends V40),
V153 (fragments), V154 (listed combinations; compound selector fields recorded), a ledger row for
Herwig's PDFs.

### Order, and verification

Order: F3 (small, a safety net), F4, F1, F2, F5; a commit each, the fast suite light between.

- Fast tests (new `tests/runner/test_selectors.py`, with a new fixture config
  `tests/fixtures/work/configs/Generators/combos.toml` added with it): F1's splices at the top level and
  in a group, `[]`, the refusals (a group in a group, a tool twice, an unknown tag in a value never
  run), per-chain interfaces; F2's rows (names, a member left out writes nothing, equal rows refused,
  `plot_points` by a member, a row without the page's member refused), compound selector fields (AE,
  BE, BG, CF); F3's refusal and a fixed unread value accepted; F4's spellings both ways, a scalar over
  `keys`, Herwig's four lines, and Pythia's own set number untouched.
- Identities: `Generators/generators --dry-run` before the first change and after the last, on one
  machine: the same identities and seeds.
- The slow suite once at the end (the generators' tests need a machine whose Herwig and Sherpa run:
  the new one).

## Notes from the fresh stack build (2026-10-15)

The reinstall is postponed (the USB would not boot: TPM/encryption). The user builds a fresh stack on this
machine instead, in a terminal of their own. What they say while it runs, to act on when ordered:

- **N1. A progress indicator while downloading.** Today `build_stack.download` copies the response in 1 MB
  chunks (`shutil.copyfileobj`) with no progress shown; a large tarball (ROOT, Geant4's data) looks like a hang.
  Wanted: bytes so far / total (`Content-Length`), the rate and an ETA, on the live line `Progress` already
  draws (`self.live`); one line per finished file when plain (`HEP_PLAIN`, no tty); the same for `fetch`'s
  downloads and pixi's (its own output, passed through).

- **N2. ROOT from source on the base: fixed (2026-10-15).** Its configure stopped on `gl2ps` (needed with
  `opengl`), and found libxml2's headers but not its library, so it turned `xml` off (conda-forge split
  `libxml2-devel` off `libxml2`). Both added to `base.toml`'s `[base.libraries] root`. CFITSIO is found the same
  half way, but ROOT does not ask for it.

- **N3. A test that reads the machine's Python path.** `test_stack_build.py::test_the_old_way_is_apt_and_a_venv`
  asserts the `base=system` script never says "pixi"; its venv is made from the running Python, which on a
  machine root with a conda base is `base/.pixi/envs/default/bin/python3`, so it fails there (not a change in
  behaviour). Fix: assert on the script's pixi commands, not on any path containing the word.

- **N4. CMake took the OS's headers on the base: fixed (2026-10-15).** ROOT's configure found gl2ps, libxml2,
  nlohmann/json, OpenGL, X11's Xinerama/Xrandr, VDT and CFITSIO in `/usr/include`, which conda's compiler never
  searches, so `TBufferJSON.cxx` failed on `nlohmann/json.hpp`. And a retry kept `forge/build/<pkg>/`, whose
  CMake cache still held those paths. Now: a CMake build starts from an empty build folder; on a Linux base,
  CMake ignores `/usr` and `/usr/local` (`build_stack.BASE_CMAKE`); the base gives ROOT `nlohmann_json` and
  OpenGL (`libgl-devel`, `libopengl-devel`, `libglx-devel`, `libglu`). The base changed, so every package built
  on it rebuilds once. A test that a CMake build on the base names those prefixes is still to write.

- **N5. YODA's HDF5 support was off: fixed (2026-10-15).** YODA's `m4/ax_lib_hdf5.m4` takes the HDF5 type from
  the wrapper's name (`*h5cc` serial, `*h5pcc` parallel, else "neither" and `.yoda.h5` off), and ours was
  `h5cc-plain`; YODA's headers still include HDF5's, so it failed on `H5Ipublic.h`. The wrapper is now
  `plain-h5cc` (`recipes/helpers/h5cc_plain.py`, the hdf5 and yoda recipes).

- **N6. A helper script's change rebuilds nothing.** `digest` hashes a recipe's fields, not the files its
  `pre`/`post` run (`recipes/helpers/h5cc_plain.py`), so N5's rename needed the helper run by hand or
  `--rebuild hdf5`. Wanted: a recipe's helpers hashed with it, as its patch is (`patch_sha256`).
  And YODA's configure keeps `.yoda.h5` on when the wrapper it is given does not exist ("HDF5 libraries... no",
  then the same compile error), so the yoda recipe should check `{dir_hdf5}/bin/plain-h5cc` exists first.
- **N7. ROOT built at `root_cores = 12` on this machine (14 GB of RAM, the conda base, 2026-10-15)**, the user's
  setting: the "3 GB a compiler" rule behind `root_cores = 0` (one per 3 GB) is cautious for ROOT here. Rivet
  built at 12 too. The rule may be loosened (or measured: peak memory per compiler).

- **N8. Rivet's analyses could not link on the base: fixed (2026-10-15).** `rivet-build` dedups its flags word
  by word (`xargs -n1 | sort -u`), which split `-isystem <base>/include` and left the bare folder on the
  linker's line ("ld: …/include: read: Is a directory"). `-isystem` is now joined to its path (`base.toml`'s
  `CPPFLAGS`, `build_stack`'s `{cflags}`, `rules.mk`'s `ON_BASE`), which GCC takes as one word.

- **N9. Pythia8's check read a PDF set not yet installed: fixed (2026-10-15).** Its check runs 100 events with
  `LHAPDF6:CT14lo`, and `pdfsets` came last in the build, so on a fresh root init failed ("unknown PDF CT14lo");
  the old machine had the sets already. `pdfsets` now comes right after `lhapdf` (in `standard.toml`, so the file
  is the order) and `pythia8` needs it.

- **N10. ThePEG took the OS's Boost: fixed (2026-10-15).** Its `boost.m4` found Boost 1.90 in `/usr/include`
  (unseen by conda's compiler) before the base's 1.92, so its unit-test check failed. `--with-boost={base}` for
  ThePEG and Herwig in `base.toml`, as zlib and GSL already were. Autotools packages have no CMake-style switch
  to keep out of `/usr` (N4): each macro that searches the OS needs pointing at the base.

- **N11. ThePEG's libraries lost crtendS.o: fixed (2026-10-15).** conda-forge's GCC 15 specs add `-L <dir>` with a
  space; the libtool in ThePEG's and Herwig's `configure` tests `x-L = "$p"` (never true; fixed in libtool 2.4.7 as
  `"x$p"`), so `postdeps` got two bare `-L`s, and `-L crtendS.o` took the end file for a folder ("undefined
  reference to __TMC_END__"). A `pre` step in `base.toml` makes the upstream fix to their `configure`. Checked: the
  other packages downloaded (LHAPDF, HepMC3, FastJet, YODA, Rivet, Pythia8, Sherpa, Whizard, Delphes, Geant4,
  MadGraph) do not carry that line.

- **N12. Whizard found OCaml 4.06: fixed (2026-10-15).** `ocaml-findlib` (in the base's Linux lists) holds OCaml at
  4.14.x, whose conda-forge builds need GCC 13 or 14; beside the base's GCC 15 the solve fell back to OCaml 4.06.1,
  too old for Whizard 3.1.8 ("found version 4.06.1, too old"). Whizard does not use findlib: dropped, and the solve
  gives OCaml 5.4.0 with GCC 15.3. But the base's lock kept 4.06.1, which `ocaml = "*"` still allows: OCaml is
  now asked for as `ocaml >=4.08` (Whizard's floor), and as a base tool, not a library (a compiler: its version
  rebuilds nothing). Whizard on OCaml 5 is yet to be built.
- **N13. Any change of the base marks the whole stack.** `base_hash` covers the versions of every library the
  base lists, and every package built on the base records it, so N12's change names ROOT and the rest as changed
  since built (not rebuilt on its own: `--rebuild` does it). The notice is noise for a package the change does not
  touch. Wanted: each
  package's digest takes the compilers and runtime, plus the base libraries it builds against (its own list and
  what its recipe names), so OCaml's change rebuilds Whizard alone.

- **N14. Whizard's OCaml build took conda's GPROF: fixed (2026-10-15).** conda's activation exports `GPROF` (its
  gprof's name); Whizard's Makefiles put `$(GPROF)` in `OCAMLOPTFLAGS` as a profiling flag and never set it, so
  ocamlopt got "x86_64-conda-linux-gnu-gprof" ("Don't know what to do with …"). `base.toml` gives Whizard
  `GPROF = ""`. The base's activation exports other tool names too (AR, NM, LD, …): a package that uses one
  of those names for something else will meet the same.

- **N15. Whizard's mcfio wanted `rpc/types.h`: fixed (2026-10-15).** glibc no longer ships SunRPC; Whizard asks
  pkg-config for `libtirpc`, which the base now gives (Whizard's list in `base.toml`).

- **N16. Whizard built without LHAPDF, as on both machines before: fixed (2026-10-15).** Its configure tests LHAPDF
  with `lhapdf-config --cxxflags` (LHAPDF 6.5: the build flags, no `-I`) and `--ldflags` (`-L` alone, no `-lLHAPDF`),
  so the test could not compile and Whizard built a dummy; the recipe's "linked" check caught it. Whizard's recipe
  now sets `CPATH` (the headers) and `LIBS` (`-lLHAPDF`, with its rpath); its configure then says "LHAPDF: yes,
  v6.5.6" (checked in the built tree).

- **N17. Geant4's data downloads inside its build, all or nothing (2026-10-15).** `geant4_data = ON` has CMake fetch
  ~2 GB of datasets during `cmake --build`; one truncated transfer (G4EMLOW 8.8, "Transferred a partial file")
  failed the package, and since N4 a retry recompiles Geant4 from an empty build folder (~20 min) before fetching
  again. Wanted: the datasets fetched by `build_stack`'s own downloader (resumed, checked, kept in forge/downloads,
  N1's progress) and given to CMake (`GEANT4_INSTALL_DATADIR` or unpacked into place), with the code built once.

- **N18. `@primary` built from source on the conda base, whole (2026-10-15)**, after N2–N17: every package and its
  checks, Geant4 on the second try (N17), MadAnalysis5 (a `status = "new"` recipe) installed. G11's first proof.
  The build's last step wrote the shell block into the real ~/.bashrc (`shell_rc` defaults on), which the user had
  asked to be asked about first: an agent running a build here passes `shell_rc=false` unless told otherwise.
  Next: `heimdall build --framework` (the apps against the new stack: identities change, the user's call) and the
  suites.

- **N19. Heimdall's apps built on the base (2026-10-15).** `App_Pythia` failed to link (`pthread_join`): the base's
  glibc 2.28 keeps threads in libpthread, which nothing linked; `rules.mk`'s `BASE` now has `-pthread`. The C++ tests
  pass. The fast suite then showed a point identity that moved with the machine root: the Delphes chain's script
  runs the base's Python, written `{machine}/base/…`, so a base kept where it was while the root's name moved
  changed it (V137's test). `paths` gains `{base}` ($HEP_BASE), longest-first like the others.
- **N20. Tests a conda-base root skips.** Seven shell tests (`test_setup.py`, `test_shellrc.py`) skip "no venv in
  the machine root": they know the venv only, so on the base they never run. The editor-schema test (`test_v3.py`)
  skips without `jsonschema`, which the venv had and the base lacks (`base_pypi` or the base's Python list).
- **N21. MadGraph made whole (2026-10-21).** The user: Pythia with HepMC2 too, for MadGraph's showers; HepMC2 in
  `@primary`; MadAnalysis 5 used by MadGraph without `install MadAnalysis5`; QCDLoop, Ninja, OneLOop, CutTools,
  IREGI, COLLIER. `hepmc2` and `qcdloop` recipes; Pythia `--with-hepmc2` (optional) and `--with-gzip` (MadGraph
  hands it `.lhe.gz`), `main164` built in its post (HepMC2 output: MadGraph's Delphes step is `DelphesHepMC2`);
  `recipes/madgraph.py` (the options, the loop libraries through MadGraph's offline installer and the tarballs
  it ships) and `recipes/madanalysis5.py` (`version.txt`, the base's zlib, SampleAnalyzer); `HEPTools/lib` on
  `LD_LIBRARY_PATH`. Seen: e+e- → μ+μ- at LO with MA5 at parton level, the shower writing HepMC2, MA5's
  reconstruction and hadron-level analysis; `check timing u u~ > d d~ [virt=QCD]` with Ninja, COLLIER, IREGI
  and CutTools. Not done: the MG5aMC_PY8 interface (MadGraph 3.8 showers with `main164`), Herwig's paths.
  Then the user's NLO shower: aMC@NLO's Pythia 8.3 driver includes two plugin headers that each define
  `PYTHIA8_PLUGIN_VERSIONS`' functions in 8.318; `madgraph.py noplugin` compiles it with `-DNOPLUGIN`.

## Audit 4: ghosts and gaps (2026-10-15)

[docs/audit_4/](../docs/audit_4/README.md), ordered by the user with task F ("initiate an audit for features and
capabilities that are present but not documented or used, abandoned halfway or not fully developed, deprecated
but still lingers as a ghost, hard to discern its purpose or usefulness"). Findings G1–G23 and a plan in four
phases; nothing built until the user orders a phase. The user decided Phase 2 on 2026-10-15 (retire G13, G14,
G15, G3, G5, G18, G16; keep G4; rename `hep.toml` to `heimdall.toml`; fix G12's messages, keep reading v2; mark
G7's unproven toolkits): docs/audit_4/02_Plan.md has the steps. Phases 1 and 2 are ready to build.

## Next: the reinstalled lab PC

The runbook is [docs/framework/](../docs/framework/README.md), P0–P4, from a clone of Heimdall (or the
bundle kept before the wipe). What it proves for the first time:
- **Rivet, ROOT, Pythia 8 and the rest built from source on the conda base.** Never finished on the old
  machine (it went down once at every core; the last try was stopped for the reinstall). `@primary`'s
  first build is the test; `root_cores` keeps ROOT's and Rivet's compilers to ~3 GB each.
- **The slow suite on a conda base.** Last baseline (old machine, `base = "system"`): 36 passed, 3 failed
  on the OS's libraries (Herwig, Sherpa, the three-generator test: exit 127).
- **The shell block.** The build writes `gjallarhorn` and `bifrost` into ~/.bashrc and ~/.zshrc
  (`shell_rc`); the old machine's real ~/.bashrc never had one (asked before writing, then the wipe).

## Not yet proven anywhere

- A real Apptainer image (`heimdall image build packages=@core-conda`, minutes; ask before the
  downloads). The old machine's `singularity` was broken (libsubid.so.4), so the tests use a fake runtime.
- Tasks A–E on the Mac.
- **`[cluster] image` is half a way (found 2026-10-14, in the cleanup pass).** The jobs run in the image,
  but `heimdall cluster` plans every point on the login node, outside it (planning reads the PDF sets,
  Rivet's data, the card checker), so the login node still needs a stack; inside the image there is no
  `sbatch`. Options, for the user: plan inside the image and have it write a `submit.sh` the host runs
  (chaining the job ids itself), or bind the site's Slurm client into the image. The docs say the limit.
- `heimdall cluster` on a real Slurm (an emulated one only; `--dry-run` first).
- docs/conda/03_Plan.md phase 3: the physics against the old stack, the tracked multi-platform lock, a
  bootstrap for clusters with Python < 3.11.

## Held: ask the user first

- **Identities:** `src/Module.hh` says `hep run` in an error string and `hep explain` in a comment;
  `src/App_yd2rt.cc` says `hep plot` in a comment. Editing Module.hh changes every module binary, so
  every point that ran one: rename them with the next deliberate rebuild.
- **The frozen fixture:** its `Makefile`'s error string names `setup.sh`; its configs' comments and
  `modules/Decay/README.md` say `hep run` (and `tests/reference/v2_configs/` mirrors the configs).
  Fixtures change only together with a test that needs it.

## Later, on the user's word

- [docs/audit_2/01_Health.md](../docs/audit_2/01_Health.md)'s R0–R3: verify the mpl pages against
  mkhtml's, after which the yoda backend goes (H11); quick fixes (a compare figure drawn once, H2);
  `runner/figures.py` and the figure-class rules in the schema; sheets, tests and docs.
- `heimdall migrate --stamp`: the stack's versions into `[config.meta].versions`.
- F8 `--more`; HTCondor and PBS for `heimdall cluster`; Paint's PDF line widths (about 2× too thick);
  the held C++/Rivet items (K3, K4, K7, K8, K10, yd2rt's dead parameter); `extends`/`common.toml` for
  validation ("not now").

## Standing constraints

- **Commits:** local, never pushed without asking, with the Co-Authored-By line; stage named paths only,
  never `commit -a`; the stack lives in the machine root `~/Himinbjorg`, outside the tree.
- **Tests:**
  - `source gjallarhorn.sh` (this Heimdall's) before make or pytest;
  - they run in the fixture work dir's copy, `$HEP_FORGE/scratch/work/` (V52, V112), never a real one;
  - one pytest session at a time, the slow suite on its own, and light: `taskset -c 0-5 nice`, and
    pytest directly rather than `make test` (its `make all` rebuilds the machine's apps);
  - a long build starts detached (`setsid nohup … < /dev/null &`), or a session's end kills it.
- **Approvals:**
  - the stack and every download need the user's approval; never write into `~/HEP` or its venv;
  - a rebuilt App_Pythia, App_yd2rt, InprocJets or Rivet plugin changes the identity of every point
    that ran it, so ask before rebuilding (Paint is plot-only and safe).
- **Docs:** after changing a schema key's `doc`/`notes`, base.toml's comments or the CLI's help, run
  `heimdall make --framework docs schema`.
- **Way of working:** never implement without an explicit order; plans first (saved here as they grow),
  questions when a request is ambiguous.
