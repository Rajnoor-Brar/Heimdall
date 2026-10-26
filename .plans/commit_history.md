# Commit history (2026-10-26)

Both repositories' commits after the squash of 2026-10-26. Heimdall's 71 unpushed commits became
milestones by plumbing only: each new commit's tree is exactly its group's last old commit's tree, so no
file changed. The originals are kept under the local tag `archive/pre-squash-2026-10-26` (`git show <old>`
still works), and a cited old hash in a tracked file reads "`<new>` (was `<old>`)". Nothing pushed was
rewritten. Brookhaven's commits were all pushed, so its pending work was committed on top instead.

## Heimdall

### On GitHub (44, unchanged)

| # | Commit | Date | Subject |
| --- | --- | --- | --- |
| 1 | `d5ef4f7` | 2026-10-11 15:11 | Initial commit |
| 2 | `99da1d3` | 2026-10-10 12:51 | Seed: the framework from High-Energy at split/base (5e0a913) |
| 3 | `3561082` | 2026-10-10 12:55 | recipes: the stack builds into Heimdall (stash/ forge/ stack/ env/venv); setup.sh tracked; env/hep_env.sh |
| 4 | `aa68dcb` | 2026-10-10 17:02 | runner: two roots, hep_root() and work_root(); {hep}/{work} in the tool folders, {repo} refused; provenance with two git states |
| 5 | `25e480d` | 2026-10-10 17:03 | recipes: toolkits — preset sets for a kind of work, isolated C++20 stacks, your own in toolkits.d |
| 6 | `c6e7590` | 2026-10-10 17:32 | hep setup and hep where, the work-dir template, the Makefile split, the comment pass |
| 7 | `8aa40ac` | 2026-10-10 18:01 | tests: a work dir of their own, run against the stack |
| 8 | `a0612e4` | 2026-10-10 18:01 | docs: the manual re-rooted for Heimdall (V105–V113); docs/framework as the fresh-machine runbook |
| 9 | `bcb9d9f` | 2026-10-11 12:04 | hep cluster: a run as Slurm jobs, configured by [cluster] (V114) |
| 10 | `6767d28` | 2026-10-12 14:16 | hep refresh: reload the shell's environment in place (V115) |
| 11 | `8cf464a` | 2026-10-12 20:17 | docs/audit_3: a user-experience audit after the first Mac build (U1–U65), and a plan in seven phases |
| 12 | `1719ba3` | 2026-10-12 21:57 | docs/audit_3: the user's decisions — toolkits as build configurations, the tool context file, versions, HDF5, v3 names |
| 13 | `1b7b614` | 2026-10-12 22:13 | docs/audit_3: cards only for the tools used — the chain plus run.generate_cards |
| 14 | `ee3fc7c` | 2026-10-12 22:24 | docs/audit_3: the machine root is ~/Himinbjorg; where the context file lives; a point lock (U66) |
| 15 | `2400618` | 2026-10-12 22:33 | phase 1.1: downloads that are verified; recipes where the releases live (V116) |
| 16 | `ecdc6dd` | 2026-10-12 22:37 | phase 1.2: a clean build environment, a preflight, explicit optional dependencies (V117) |
| 17 | `94d3eab` | 2026-10-12 22:43 | phase 1.3: the Mac's fixes as recipe lines; stamps that know their recipe; rebuilds; progress (V118) |
| 18 | `06afd05` | 2026-10-12 22:52 | phase 2.1: hep doctor — every package's checks from its recipe, the library scan (V119) |
| 19 | `7ae1908` | 2026-10-12 22:55 | phase 2.2: a support matrix, a second machine in the loop, the macOS annex from the real build (V120) |
| 20 | `2d81a51` | 2026-10-12 22:58 | phase 2.3: --rebuild-broken after an OS upgrade; each build records its system libraries (V121) |
| 21 | `d3da2be` | 2026-10-12 23:30 | phase 3.1: the machine root ~/Himinbjorg — what a machine built, outside the checkout (V122) |
| 22 | `ee2dc94` | 2026-10-13 02:42 | phase 3.2: toolkits as files, one package registry (V123) |
| 23 | `798303d` | 2026-10-13 02:59 | phase 3.3: the shell — bash only, one stack at a time, a quit that undoes everything (V124) |
| 24 | `cd8a1b7` | 2026-10-13 03:01 | phase 4.1: the tool search path — work dir, machine root, Heimdall (V125) |
| 25 | `2ae2d22` | 2026-10-13 03:32 | phase 4.2: one context file per point; exec and module as folders; module settings checked (V126) |
| 26 | `df0ae0a` | 2026-10-13 03:43 | phase 4.3: a study's own layers — style, vocabulary, LaTeX; plot code in framework/plot (V127) |
| 27 | `1737f7a` | 2026-10-13 04:10 | phase 6.1: schema v3, read as v2; a quantity that changes nothing is refused (V128) |
| 28 | `55261820` | 2026-10-13 04:12 | phase 6.2: the card's origins; a v3 file's imported tool tables merge (V129) |
| 29 | `2ebca88` | 2026-10-13 10:06 | docs/audit_3: a work dir in a git repository — U67, plan step 5.3 |
| 30 | `9743348` | 2026-10-13 10:21 | phase 6.3 (1/2): hep migrate --v3; the fixture and the starter in v3; errors cross tables (V130) |
| 31 | `3297641` | 2026-10-13 10:37 | phase 6.3 (2a): hep check, explain, show-config, editor schemas; hep in UTF-8 mode |
| 32 | `feaf3ec` | 2026-10-13 10:54 | phase 6.3 (2b): v3 serials; one meaning of "default"; --set in a v3 file's names |
| 33 | `628ec9a` | 2026-10-13 11:11 | phase 6.3 (2c): the manual on v3; v3 names in imports and errors (V131) |
| 34 | `ecd221a` | 2026-10-13 17:24 | phase 5.1: records/, logs/ and .cache/; a point lock (V132) |
| 35 | `28e2665` | 2026-10-13 17:28 | phase 5.2–5.3: decks/, datasets.toml, setup --refresh; a work dir in a git repository (V133) |
| 36 | `bf75f19` | 2026-10-13 17:39 | phase 7.1: one command line (V134) |
| 37 | `8d43d89` | 2026-10-13 17:42 | phase 7.2: the first run (V135) |
| 38 | `fc798e0` | 2026-10-13 17:46 | phase 7.3: docs that match the code; docs/00_Quick.md (V136) |
| 39 | `60b6e4c` | 2026-10-14 01:04 | Fingerprints name no folder (V137) |
| 40 | `ebf31df` | 2026-10-14 01:04 | The user pages without the record's ids (V138) |
| 41 | `864c0f4` | 2026-10-14 01:04 | What porting a real study found (V139; records V137–V139) |
| 42 | `e20681f` | 2026-10-14 02:00 | docs/conda: a conda base for the machine root, the design |
| 43 | `c643ebe` | 2026-10-14 14:19 | The conda base, the default; ready-made toolkits (V140, V141) |
| 44 | `3e97b6a` | 2026-10-14 14:19 | bots: task B's plan (heimdall, bifrost, recognise) and its drafts |

### After the squash (unpushed)

| Commit | Date | Subject | Holds |
| --- | --- | --- | --- |
| `49fe1ff` | 2026-10-15 11:56 | Tasks B–F and audit 4: heimdall, gjallarhorn, recognise and bifrost; the machine's own recipes and tool packages; a run keeps little; Apptainer images; the encoding named everywhere; varied values, one pdf, chain pieces, listed points (V142–V154) | 27 old: `aef04b3`…`69a6c38` |
| `fb3eed8` | 2026-10-21 17:27 | The stack built whole on the conda base: its first build's fixes (ROOT, CMake, HDF5, rivet-build, LHAPDF sets, Herwig, OCaml and Whizard, Geant4, the apps); MadGraph with HepMC2, its loops and MadAnalysis 5 (V155) | 21 old: `a4d4f3d`…`4bf2e06` |
| `db96104` | 2026-10-22 12:30 | Task H: what a run shows, one records/ tree, a run's snapshot, pages of chosen points and their statistics; editor/ from High-Energy; High-Energy a work dir (V156–V162) | 11 old: `db38c72`…`7b71a73` |
| `fde73d0` | 2026-10-23 08:28 | Plot documents: plots and statistics by set, a document per run, the runs together; documents as run TOMLs, standings and tables, a configuration's own cards and data (V163–V180) | 2 old: `4477c17`…`a403177` |
| `5c271a0` | 2026-10-25 17:20 | Task L: detachable runs, heimdall stop and the run registry; [heimdall]; NLO in Sherpa; pending work in ISSUES.md (V181–V189) | 4 old: `fb6b28f`…`29b27ae` |
| `64a472e` | 2026-10-26 08:56 | Phase 1: Task L's follow-ups, the stack's build, small defects; .plans/ (V190–V194) | 5 old: `587d87b`…`5663f57` |
| `d13442d` | 2026-10-26 09:27 | Run logging L1: clean saved text, Sherpa's mid-line messages, the stall's context (V195) | `797fc4e` |

### Old → new

| Old | Date | Subject | Now in |
| --- | --- | --- | --- |
| `aef04b3` | 2026-10-14 14:37 | bots: heimdall bifrost adds packages to the environment (task B, step 3b) | `49fe1ff` |
| `004ae82` | 2026-10-14 14:39 | bots: gjallarhorn loads the environment, bifrost manages its packages (task B) | `49fe1ff` |
| `c048048` | 2026-10-14 14:50 | The program is heimdall; the loader is gjallarhorn.sh (V142) | `49fe1ff` |
| `12f3dd7` | 2026-10-14 15:10 | heimdall recognise: the work dirs a machine knows, by title (V143, part 1) | `49fe1ff` |
| `645f795` | 2026-10-14 15:16 | gjallarhorn [title], and the shell's block of it (V143) | `49fe1ff` |
| `4b39be2` | 2026-10-14 17:34 | bifrost: the environment's packages (V144) | `49fe1ff` |
| `af7377b` | 2026-10-14 17:36 | The quick starts with gjallarhorn and bifrost (task B, done) | `49fe1ff` |
| `4ffec9c` | 2026-10-14 18:21 | bots: task C, tools by flag (bifrost -c / -b / -b@toolkit), recipes.toml, gated flags | `49fe1ff` |
| `2dd98d8` | 2026-10-14 18:47 | The machine's own recipes, flags gated by version, a tool with a toolkit's changes (V145) | `49fe1ff` |
| `fceb64b` | 2026-10-14 18:51 | A tool folder names its packages (V146) | `49fe1ff` |
| `6fd3458` | 2026-10-14 18:56 | bifrost -c and -b: a tool ready-made or built, and what a switch costs (V147) | `49fe1ff` |
| `51c0ed6` | 2026-10-14 19:04 | Libraries and programs of one's own: pkg: requires, tools new --package (V148) | `49fe1ff` |
| `21cea11` | 2026-10-14 19:53 | A run keeps little unless told (V149) | `49fe1ff` |
| `2d9f097` | 2026-10-14 20:00 | Apptainer images (V150) | `49fe1ff` |
| `0326634` | 2026-10-14 20:07 | Two slow tests ask to keep the working files they read (V149) | `49fe1ff` |
| `d3cdfc3` | 2026-10-14 22:53 | Name the encoding on every text read, write and pipe (L17) | `49fe1ff` |
| `d3cd4c8` | 2026-10-14 22:53 | A run with the machine root read-only writes only its work dir (V150) | `49fe1ff` |
| `79a113c` | 2026-10-14 22:53 | The manual, the runbook and the recipes say what was built (V140–V150) | `49fe1ff` |
| `549cfbf` | 2026-10-14 22:53 | bots: tasks A–E archived; the plan says only what is open | `49fe1ff` |
| `3bdd4ea` | 2026-10-15 00:09 | A varied value every point reads (V151) | `49fe1ff` |
| `292546d` | 2026-10-15 00:14 | One pdf for every generator (V152) | `49fe1ff` |
| `8d75401` | 2026-10-15 00:20 | A selector's value may be a piece of chain (V153) | `49fe1ff` |
| `31f24be` | 2026-10-15 00:28 | Points that set several quantities at once (V154) | `49fe1ff` |
| `d9d6374` | 2026-10-15 00:29 | The manual on comparing generators and tool setups (task F) | `49fe1ff` |
| `b0cc1c4` | 2026-10-15 00:38 | Audit 4: ghosts and gaps (G1–G23) | `49fe1ff` |
| `66c1456` | 2026-10-15 11:52 | Audit 4's further sweeps; task G set aside in intent.md | `49fe1ff` |
| `69a6c38` | 2026-10-15 11:56 | Audit 4: the user's Phase 2 decisions | `49fe1ff` |
| `a4d4f3d` | 2026-10-15 12:22 | bots: notes from the fresh stack build (N1: download progress) | `fb3eed8` |
| `e94012c` | 2026-10-15 12:29 | The base gives ROOT gl2ps and libxml2-devel | `fb3eed8` |
| `40cdb0e` | 2026-10-15 12:29 | bots: N3, a stack-build test that reads the machine's Python path | `fb3eed8` |
| `72fa669` | 2026-10-15 15:01 | CMake on the base keeps out of /usr, from an empty build folder | `fb3eed8` |
| `8d43427` | 2026-10-15 15:26 | The HDF5 wrapper is plain-h5cc, so YODA sees a serial HDF5 | `fb3eed8` |
| `28fa79a` | 2026-10-15 15:29 | bots: N6 (helpers outside the recipe digest), N7 (ROOT at 12 compilers on 14 GB) | `fb3eed8` |
| `34122ad` | 2026-10-15 15:49 | -isystem joined to its path, so rivet-build keeps it whole | `fb3eed8` |
| `95711d3` | 2026-10-15 16:31 | PDF sets right after LHAPDF, before Pythia8's check reads one | `fb3eed8` |
| `0a9d1f6` | 2026-10-15 16:46 | ThePEG and Herwig take the base's Boost | `fb3eed8` |
| `44ae336` | 2026-10-15 16:52 | ThePEG and Herwig: libtool's -L fix, for the base's GCC | `fb3eed8` |
| `58abef7` | 2026-10-15 18:31 | The base without ocaml-findlib, so OCaml can be new enough for Whizard | `fb3eed8` |
| `052c76b` | 2026-10-15 18:37 | OCaml a base tool, asked for at >=4.08 (Whizard's floor) | `fb3eed8` |
| `e993735` | 2026-10-15 18:40 | Whizard builds with GPROF empty | `fb3eed8` |
| `97794b0` | 2026-10-15 18:41 | The base gives Whizard libtirpc | `fb3eed8` |
| `4c1772b` | 2026-10-15 18:49 | Whizard finds LHAPDF: CPATH and LIBS for its test and link | `fb3eed8` |
| `ed10059` | 2026-10-15 19:42 | bots: N17, Geant4's data fetched inside its build | `fb3eed8` |
| `ce4602e` | 2026-10-15 19:48 | bots: N18, @primary built whole on the conda base | `fb3eed8` |
| `b6fe9e8` | 2026-10-15 20:02 | Heimdall's apps on the conda base: -pthread, and a {base} placeholder | `fb3eed8` |
| `cb3ff55` | 2026-10-21 17:01 | MadGraph on the whole stack: HepMC2, its loop libraries, MadAnalysis 5 (V155) | `fb3eed8` |
| `8fa24bb` | 2026-10-21 17:01 | The V151 hint's second line: a literal brace, not an f-string's doubled one | `fb3eed8` |
| `4bf2e06` | 2026-10-21 17:27 | aMC@NLO's Pythia 8.3 driver compiled with -DNOPLUGIN | `fb3eed8` |
| `db38c72` | 2026-10-21 23:46 | What a run shows: finish times, the view's note line, Sherpa's progress (V156) | `db96104` |
| `2ea5de2` | 2026-10-22 00:08 | One records/ tree; points in points/ (V157) | `db96104` |
| `6cc01f1` | 2026-10-22 00:23 | A run's snapshot; a record is a config; pages from what was recorded (V158) | `db96104` |
| `479a23c` | 2026-10-22 11:45 | Pages of chosen points; page statistics (V159, V160) | `db96104` |
| `2186975` | 2026-10-22 11:48 | editor/: the VS Code tooling, from High-Energy's aux/ (2c4fcad) | `db96104` |
| `3866c20` | 2026-10-22 11:50 | A snapshot copies every import, not only imported runs (V158) | `db96104` |
| `fa497d6` | 2026-10-22 11:52 | High-Energy is a work dir; aux/ is editor/ (V161) | `db96104` |
| `67434ff` | 2026-10-22 12:11 | Slow tests on the records/ tree: the journal, shards, support (V157) | `db96104` |
| `c8653b2` | 2026-10-22 12:11 | bots: the slow suite on the conda base; the legacy gates' one digit | `db96104` |
| `3a6560c` | 2026-10-22 12:11 | bots: 38 of 41 slow tests, not 39 | `db96104` |
| `7b71a73` | 2026-10-22 12:30 | statistics.csv as bar graphs, in plots/statistics/ (V162) | `db96104` |
| `4477c17` | 2026-10-22 22:16 | Plots and statistics by set, a plot document per run, the runs together (V163-V171) | `fde73d0` |
| `a403177` | 2026-10-23 08:28 | Plot documents as run TOMLs; the statistics summary as standings and tables; a configuration's own cards and data (V172-V180) | `fde73d0` |
| `fb6b28f` | 2026-10-25 17:19 | Detachable runs, heimdall stop and a run registry; a legend outside the frame; compound sets; a point keeps its commands (V181-V187) | `5c271a0` |
| `a7675e6` | 2026-10-25 17:19 | [heimdall]: a command's flags from its run TOML (V188) | `5c271a0` |
| `ed081b5` | 2026-10-25 17:19 | NLO in Sherpa: the one-loop providers and @loops; Amegic's compile in the prepare step (V189) | `5c271a0` |
| `29b27ae` | 2026-10-25 17:20 | Pending work in ISSUES.md; the plan files and bots/ removed | `5c271a0` |
| `587d87b` | 2026-10-25 18:25 | Task L's follow-ups: [heimdall] takes preference switches; the registry reads only your own entries (V190, V191) | `64a472e` |
| `1ffd8c8` | 2026-10-25 18:25 | The stack's build: compilers from the free CPUs and memory; every recipe built here pinned (V192, V193) | `64a472e` |
| `eb49516` | 2026-10-25 18:25 | Small defects (V194); ISSUES.md: the approved plan, Phase 1's issues closed | `64a472e` |
| `0577eca` | 2026-10-25 18:44 | ISSUES.md: two slow-suite failures (I-09, I-79) | `64a472e` |
| `5663f57` | 2026-10-26 08:56 | .plans/: ISSUES.md, the plans and the run-logging audit | `64a472e` |
| `797fc4e` | 2026-10-26 09:27 | Run logging L1: clean saved text, Sherpa's mid-line messages, the stall's context (V195) | `d13442d` |

## Brookhaven

All three of its earlier commits were on GitHub, so none was rewritten. Its pending work (the
PhotoProduction configs moved to `configs/legacy/`, and the untracked `configs/eic/` and `configs/zeus/`)
is two new commits on top.

| # | Commit | Date | Subject | Where |
| --- | --- | --- | --- | --- |
| 1 | `3e4ac59` | 2026-10-13 10:06 | Initial commit | GitHub |
| 2 | `91c0a44` | 2026-10-14 01:05 | hep setup: the work dir Brookhaven (Heimdall 864c0f498dee) | GitHub |
| 3 | `ea43a70` | 2026-10-14 01:05 | PhotoProduction, from High-Energy | GitHub |
| 4 | `19d407f` | 2026-10-26 10:22 | The PhotoProduction study kept as configs/legacy/ | local |
| 5 | `a383ef1` | 2026-10-26 10:22 | The EIC and ZEUS studies: configs/eic/ and configs/zeus/ | local |
