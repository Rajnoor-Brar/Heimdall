---
id: build-fixes-generators
summary: why the generator recipes are written as they are: each problem a build hit and what is done about it
code: recipes/toolkits/standard.toml, recipes/madgraph.py, recipes/madanalysis5.py
---

# Build fixes: the generators

Each was hit on a real build. The core: [build-fixes](build-fixes.md).

| Package | Problem | What is done |
|---|---|---|
| ThePEG | `--with-hepmc` alone looks for HepMC2 | `--with-hepmcversion=3` |
| Herwig | `make install` writes `HerwigDefaults.rpo`, which needs CT14lo/CT14nlo | `lhapdf install CT14lo CT14nlo` first, `LHAPDF_DATA_PATH` set |
| Delphes | DelphesPythia8 is built only when Pythia8 is found | `PYTHIA8=<install>` in its environment, `-DROOT_DIR=<root>/cmake` |
| Sherpa | its `_DIR` options are spelled per package (`HepMC3_DIR`, `RIVET_DIR`, `FASTJET_DIR`, `LHAPDF_DIR`) | as Sherpa spells them; `HepMC3_DIR` is the CMake config directory |
| Sherpa | its one-loop interfaces (BlackHat, OpenLoops, Recola) are built only when told, and only against an installed provider: Sherpa ships the interfaces, not the providers | `optional`: `-DSHERPA_ENABLE_<X>=ON -D<X>_DIR=…` for each provider installed; `--rebuild sherpa` after adding one |
| QD, BlackHat | their tarballs' libtool misreads the conda compiler's link line (a bare `-L` before `crtendS.o`: "undefined reference to `__TMC_END__`") | `autoreconf -fi` first (their `pre`) |
| BlackHat | 0.9.9 is from 2013: GCC 4.8, 6 and 10 refuse it; its `configure.ac` has automake's `-Werror`, which today's automake trips (`AM_PROG_AR`); GCC 15 refuses one `return` of an object for a pointer (`cached_OLHA.cpp`) | CMS's tree (cms-externals/blackhat, `cms/v0.9.9`: the GCC 4.8/6/10 fixes) and `recipes/patches/blackhat-0.9.9-gcc15.patch` (the other two); `root_cores` compilers, its amplitude files taking up to ~1 GB each |
| OpenLoops | not installed by a build system: built and used in its own folder, by its own scons, which must run there; its process libraries are fetched by name, and Sherpa's CMake needs the process list that only a first one brings | unpacked into `stack/openloops`; `./scons`, then `./openloops libinstall` of `settings.toml`'s `openloops_processes` (one at least) |
| Sherpa, OpenMPI | Sherpa's `SHERPA_ENABLE_MPI` is the Message Passing Interface (integration and event generation across `mpirun -n N` ranks; not multiple interactions, which are `MI_HANDLER`); it needs an MPI it finds by `mpicxx` | the `openmpi` recipe (OpenMPI, its own hwloc, libevent, PMIx and PRRTE), and `optional`: `-DSHERPA_ENABLE_MPI=ON -DMPI_HOME=<openmpi>`; one machine's ranks (a cluster's nodes want the site's MPI) |
| Recola | it links COLLIER without a run path, and MadGraph's `HEPTools/lib`, first on `LD_LIBRARY_PATH`, holds another `libcollier.so` | its own `collier` recipe, found by its CMake config (`-Dcollier_path=<collier>/lib/cmake`), and `-DCMAKE_INSTALL_RPATH_USE_LINK_PATH=ON`: an rpath goes before `LD_LIBRARY_PATH` |
| Whizard | HepMC3 is `--enable-hepmc --with-hepmc` (no `*hepmc3` options); O'Mega needs OCaml | so; OCaml from the base (`ocaml`, `bdw-gc`; not `ocaml-findlib`, whose builds hold OCaml at 4.14, made with GCC 13–14 only), or apt's `ocaml ocaml-findlib libgc-dev` |
| MadGraph | not built: a tree that finds the other tools through its configuration file, and installs its loop libraries and MadAnalysis 5 at its prompt (`install …`, from the web) | unpacked into `stack/madgraph`; `recipes/madgraph.py` sets `lhapdf_py3`, `fastjet`, `pythia8_path`, `hepmc_path` (HepMC2), `delphes_path`, `rivet_path`, `yoda_path`, `madanalysis5_path` (a path not built here is left alone) and `automatic_html_opening = False`, then builds Ninja and OneLOop, COLLIER (into `HEPTools/`), CutTools and IREGI from the tarballs it ships, through its own offline installer |
| MadGraph | its LO shower runs Pythia's `examples/main164`, which nothing builds; it hands Pythia `.lhe.gz` ("Les Houches initialization failed" without gzip); its Delphes step runs `DelphesHepMC2` | Pythia8 `--with-gzip` (the base's zlib: `base.toml`), and `main164` built in its `post`, writing HepMC2 when Pythia has it |
| MadGraph | aMC@NLO's Pythia8 driver includes `aMCatNLOHooks.h` and `CombineMatchingInput.h`, and in Pythia 8.318 each plugin header defines the same `PYTHIA8_PLUGIN_VERSIONS` functions ("redefinition of `CHECK_COMPATIBLE_VERSION`") | `recipes/madgraph.py noplugin`: its `Pythia83` rule compiles with `-DNOPLUGIN` (in `Template/`; give it an existing process folder's `MCatNLO/` too) |
| MadGraph | MadLoop's programs link the shared Ninja and COLLIER without a run path (`libninja.so.0: cannot open shared object file`); MadGraph asks the user to put `HEPTools/lib` on `LD_LIBRARY_PATH` | `env/heimdall_env.sh` does |
| QCDLoop | MadGraph's tarball carries a macOS build (objects, a configured Makefile: `install QCDLoop` installs `.dylib`s on Linux); gfortran 10+ refuses its argument mismatches | `make distclean` first; `FFLAGS=-std=legacy` |
| MadAnalysis 5 | its GitHub tarball lacks the `version.txt` its interpreter (MadGraph starts it so) reads; on the base it takes zlib from `/usr/include`; a failed compile still exits 0; its Delphes interface wants a Delphes source tree | `recipes/madanalysis5.py`: the file written, `zlib_includes` from the base, the core library checked, the Delphes interface off (as MadGraph's installer has it) |
