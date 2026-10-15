# Intent — ideas worth building, and loose ends

> Audit 1 (V52–V89, its pages in git: `git show 3a5ec16:docs/audit_1/06_Plan.md`) built several ideas here
> or scheduled them (U3/U7/U8/U9, CF2, CF3 as audit F5, F7, F4, F10, F2, B9). The ids here are this file's own:
> T (throughput), U (commands), CF (configuration), P (provenance), and F10–F14, which are the record's findings.

Collected on 2026-09-27 while reading every document before the doc set was replaced: v1's design
set (at `rework/v1-final`: `docs/rework/`, `docs/post_rework/`, `GUIDE.md`, `MAP.md`), v1's
retrospective (`docs/rework_v1/`), and the rework v2 plan and phase logs (`docs/rework_v2/`, in git
history). **None of this is implemented.** Each row names where the idea came from, what it would
cost, and why it is worth it. The manual's record (`docs/07_Record.md`) holds what was decided; this
file holds what might be.

## 1. Throughput

| # | Idea | Source | Cost | Why |
|---|---|---|---|---|
| T1 | **Per-group identity and skip.** A point reruns only the groups whose identity changed, when the earlier groups' products are complete. | P3 S1 measured it: changing yd2rt's `select` reran the whole point, 16.1 s instead of 0.2 s | medium: identity per group, products kept per group, skip per group | the cheapest kind of rerun (restyling a conversion, a post-processing tool) stops costing a generation |
| T2 | **Shared generation for analysis-option sweeps.** Points whose generator identity is the same share one generation; Rivet runs every variant in one pass (`-a photo_eic:R=0.4 -a photo_eic:R=0.7`). | v1's event groups and aliases (`docs/rework/03_Configuration.md` §4); V9's trigger | medium-high: needs T1's per-step identity, and a product that holds several variants | `radius` is 3 generations today, 1 in v1 |
| T3 | ~~**Points in parallel**~~ — **built 2026-09-30 as V36** (`parallelism = K`; `threads` stays per point, set it by hand). | 06 §5.2 | done | sweeps of many short points |
| T5 | ~~**Sharded Rivet**~~ — **built 2026-09-29 as V31** (`shards = K`, App_Pythia deal groups and parallel formatting). Left: shards on other folders (a module program with a merge tool), and choosing K from `threads` automatically. | L27, the user's "20 threads, 4 % CPU" | small each | a Pythia → Rivet point is capped by one Rivet core |
| T4 | **Weight variations as a band.** Rivet writes `/x[MUR2_MUF2]`-style variations (Sherpa on-the-fly, Pythia UncertaintyBands); Paint draws their envelope instead of dropping them. | v1 roadmap §4 ("weight variations instead of re-generation"); P4 S2 (Sherpa's variations dropped from pages) | medium: the variation objects into the merged file, an envelope in Draw.hh, a `[curves]` style key | scale and PDF uncertainty without extra generations |

## 2. Commands and views

| # | Idea | Source | Cost | Why |
|---|---|---|---|---|
| U1 | **`heimdall plot --suggest-data-map`**: print `[plot.data.map]` lines matched by name, for the user to check and paste. The map stays explicit. | v1 06_Lessons §4 (00/B5): "a suggestion the user must paste" | small | twelve map lines typed by hand for every ZEUS-style comparison |
| U2 | **`heimdall show POINT`**: a point's provenance, σ and counts from the sidecars and the YODA, cards, binaries, versions, warnings from the logs. | v1 GUIDE §3, 06_Terminal §5 | small | "why did this number change" without opening four JSON files |
| U3 | **`heimdall list CONFIG`**: the configurations, their descriptions, point counts and how many are complete. | v1 `heimdall studies` | small | the first thing to type in an unfamiliar run TOML |
| U4 | **`heimdall run --detach`** (setsid, plain log) and **`heimdall runs`** (active and recent jobs, from the journals). | v1 06_Terminal §6 | small-medium | multi-hour runs on the lab PC from a laptop session |
| U5 | **Shell completion** for `heimdall run`: configs, configuration names, point tags. | v1 08_CLI §2 | small | typing `energy_pdf` and `27x920_NNPDF23lo` |
| U6 | **`--plan --json`**, for scripts and agents. | v1 08_CLI (global `--json`) | small | a machine-readable plan without parsing text |
| U7 | **A page gallery** `plots/root/index.html` (one HTML page of the PNGs per cell), as mkhtml has. | v1 roadmap §4 ("shareable plot gallery") | small | browsing 68 pages |
| U8 | **`heimdall run --check`**: each tool's cheap preflight without events (Pythia `init()` on the point card, `rivet --list-analyses`, a card parse). Must not open a FIFO (v1's 00/B33). | v1 `hep-run --check` (03_Configuration §6) | medium | a bad card found in seconds, not after the first point's generation |
| U9 | Notify when a run ends (`notify-send` / `osascript`). | v1 06_Terminal §6 | tiny | long runs |

## 3. Configuration

| # | Idea | Source | Cost | Why |
|---|---|---|---|---|
| CF1 | **Refuse a v1 config by name.** A file with `schema`, `[study.*]`, `[generator]` or `[quantity.*]` gets "this is a v1 (hekit) run TOML" with a hint (`git show HEAD:<file>`, or the translation table), instead of "unknown section [schema]". | 2026-09-27: `jets.toml` was reverted to v1 by accident | tiny | the error then says what happened |
| CF2 | **Shared blocks between run TOMLs** (`[master] include = [...]`, tables deep-merged), e.g. the ZEUS `[plot.data.map]` and the tool tables that `jets.toml` and `validation.toml` both carry. | v1 `extends` (03_Configuration §2) | medium: precedence, where errors point | one data map, one tool setup |
| CF3 | **`--explain KEY`**: where a resolved value came from (master, quantity, static, `--set`; base.toml, root_style, `[plot.style]`, object style). | v1 `heimdall plan --explain` | small-medium | the layers are four deep for style |
| CF4 | A machine file (threads, per host). | v1 machine.toml | small | lab PC (20 threads) and Mac |

## 4. Provenance

| # | Idea | Source | Cost | Why |
|---|---|---|---|---|
| P1 | **A product that identifies itself**: the point, its identity, the git revision and the config in the YODA (annotations on `/_EVTCOUNT`) and ROOT files (a TNamed), so a copied file still says where it came from. | v1 07_Outputs §2 | small | provenance.json now lives in `output/`, away from the products |
| P2 | A run index over the provenance files (SQLite: "every point with pdf = NNPDF23lo"). | v1 roadmap §4 | medium | when there are hundreds of points |

## 5. Physics set-ups (open with the user)

- An **ep Delphes card**: the ATLAS card reconstructs a jet in 0.9% of events at these ep energies (P4 S2).
- **Herwig photoproduction**: `dis_ep.herwig.in` is NC DIS, a chain check only (P4 S2).
- A **Geant4 simulation module**: Geant4 builds (`// requires: geant4`), no program is written (P4 S3).

## 6. Loose ends found while documenting (small; each is a finding in the record, F10–F14)

| # | What | Fix |
|---|---|---|
| F10 | ~~`status_client.py` is in the runner's rank table but does not exist.~~ | **closed by V53** (dropped from the one rank table) |
| F11 | The master mapping form `render = "fn"` is described in `master.toml`'s header, but `tools._render` refuses it ("render mappings arrive with their tool"). Render tools take plain `key` mappings and apply them in `render.py`. | drop `render` from the header, or implement it |
| F12 | Card style `"prepend"` is accepted by the folder check (`CARD_STYLES`) but raises when used; Whizard's point-card-first dialect is `render.py`. | remove it from `CARD_STYLES` |
| F13 | `filters.toml`'s `[defaults] last_line = true` is never read: the last log line is always shown. | drop the table from the folders |
| F14 | The venv still holds v1's editable `hekit` install and its dead `hep` entry point (shadowed by `utils/Env` on `PATH`). | uninstall it, with approval (the venv is the user's) |

## 7. A tool's own dependencies, private to it (task G, set aside 2026-10-15)

Planned on the user's question, then set aside by the user ("scratch this"), kept here as written.

**The user's question (2026-10-15):** "Consider scenarios like BeAGLE which requires Pythia6. How can case where a
tool (built) requires other version of another tool. Likely we would prefer dependency like this to be installed
within tools dir (here BeAGLE). If there a way to handle situations like this in heimdall already or, how would we
design or add such usability". 

**What exists (read from the code):**
- **Another package is just another recipe.** Pythia 6 is not Pythia 8: `[packages.pythia6]` installs to
  `stack/pythia6`, and its libraries' names differ from Pythia 8's, so both can sit on the paths.
- **Every install is on every path.** `env/hep_env.sh` puts each install folder (the shipped list,
  `env/packages.sh`, and what a build made, `stack/.stamps/folders`) on `PATH`, `LD_LIBRARY_PATH`, `PYTHONPATH`,
  `CMAKE_PREFIX_PATH` and `PKG_CONFIG_PATH`. Two versions of one package (LHAPDF 5 and 6: both `libLHAPDF.so`
  and `lhapdf-config`; HepMC 2 and 3) cannot both be there.
- **`install = "<other>"`** puts a recipe into another's folder (ThePEG into `stack/herwig7`). That folder is
  on the paths: it is shared, not private.
- **An isolated toolkit** (`stacks/<toolkit>/`, V110) is a whole second stack in a shell of its own. It suits
  another C++ standard. One tool's dependency does not need it, and the runner cannot chain a tool of that
  stack with Rivet of this one.
- **A tool folder's `[command] env`** sets variables for its process (Rivet's `RIVET_ANALYSIS_PATH`). It
  replaces a variable (`env.update`) and cannot prepend, and it has no placeholder for a recipe's folder.

**The design:**
1. **`private` in a recipe.** `private = ["pythia6", "dpmjet"]`, or `{ lhapdf = "5.9.1" }` to give another
   release. Each named recipe is built first, from its own recipe (its `needs`, `kind`, `args`), into
   `stack/<dependent>/private/<name>/`. `{dir_<name>}` in the dependent's recipe names that copy.
   - A private copy is never on the shell's paths. It is not in `.stamps/folders` or `env/packages.sh`.
   - During the dependent's build only, its `bin/`, `lib/`, `include/` and `pkgconfig/` are on the build's
     paths, and `-Wl,-rpath,<private>/lib` is added to `{ldflags}`. The dependent's binaries then find
     it with no `LD_LIBRARY_PATH`.
   - Its stamp is the dependent's: the dependent's recipe digest includes the private recipes'. A
     change to either rebuilds the dependent, and `--rebuild` takes both.
   - Several dependents may each have their own copy, even at different releases.
2. **`scope = "private"` on a recipe** (Pythia 6, DPMJet, LHAPDF 5): one that is built only as a
   dependent's private copy, never into `stack/` on its own. `heimdall stack list` and `bifrost` say so.
   A shared recipe (LHAPDF 6) may still be named in `private` with another release.
3. **The tool side.**
   - A tool folder's `{package}` placeholder is its first `[tool] packages` recipe's folder, e.g.
     `executable = "{package}/BeAGLE"`.
   - `[command] env` gains a prepend form for path lists: `LD_LIBRARY_PATH = ["{package}/private/x/lib"]`,
     a list put before the shell's. This is for the rare program that rpath cannot reach.
   - Data a tool reads from its run folder (BeAGLE's `nuclear.bin`) is a prepare step or a `[prelim]` file,
     as today.
4. **Provenance and checks.**
   - A point's package states (V146) give each private copy's release: "beagle 1.03 (private: pythia6
     6.4.28, dpmjet 3.0)".
   - The tool's binaries' sha256 are already in its identity.
   - `heimdall doctor`'s library scan reads `<dependent>/private/` too, so a broken private library is named.
5. **Docs and record:** recipes/README §2 (a recipe's private dependencies, with BeAGLE as the example),
   05 §9's tool-folder keys (`{package}`, prepend `env`), 06 §16; a V-row.

**BeAGLE itself, to be checked against its README before writing its recipe**
([gitlab.in2p3.fr/BeAGLE/BeAGLE](https://gitlab.in2p3.fr/BeAGLE/BeAGLE)):
- the EIC page says it couples DPMJet 3 (the nucleus) and PYTHIA (the elementary interaction, linked to
  LHAPDF for EPS09 nuclear PDFs) with PyQM;
- it builds with `make all` after copying RAPGAP 3.302's static libraries in;
- `$BEAGLESYS` names its folder;
- it reads FLUKA's `nuclear.bin` from the run folder;
- its events are a text record that eic-smear converts to ROOT. For Rivet, a chain needs a converter to
  HepMC, unless the version used writes HepMC itself.
