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
