---
id: build-fixes
summary: why the core recipes are written as they are: each problem a build hit and what is done about it
code: recipes/toolkits/standard.toml, recipes/base.toml
---

# Build fixes: the core

Each was hit on a real build, and the recipes do what the right column says. Before changing a recipe, read its row. The generators: [build-fixes-generators](build-fixes-generators.md).

| Package | Problem | What is done |
|---|---|---|
| all | ROOT, Rivet, Pythia8 and the module programs pass C++ types across libraries: mixed standards are ABI trouble | one standard for everything: `CXXFLAGS="-O2 -std=c++17"` for every build, and `CMAKE_CXX_STANDARD=17` |
| all | the build of one package needs the ones before it on its paths | the base's (or venv's) `bin/` first on `PATH`, and every install on `PATH`, `LD_LIBRARY_PATH` and `PYTHONPATH`, as `gjallarhorn.sh` gives them later (`settings.toml [env]` for the rest) |
| all, on the base | conda's GCC searches its own sysroot, not `/usr`; a program built on the base needs the base's `libstdc++` at run time | every build inside the base's activation, `-isystem <base>/include` and `-Wl,-rpath,<base>/lib` (`{cflags}`, `{cxxflags}`, `{ldflags}`); `<base>/lib` never on `LD_LIBRARY_PATH` |
| YODA, Rivet, ThePEG, Herwig | on the base, their configure looks for zlib in `/usr/local /usr` (adding `-I/usr/include`: the OS's glibc headers among the base's, "bits/timesize.h: No such file") and for GSL on "the system" | `--with-zlib=<base>`, `--with-gsl=<base>` (`base.toml`) |
| the base | conda-forge's ROOT is built against glibc 2.17's headers and pins that sysroot; the compilers alone get 2.28 | the sysroot unpinned in `base.toml`: the newest the solve allows |
| the base | conda-forge's toml++ (header-only) ships a CMake config and no pkg-config file, which `env/stack.toml`'s probe asks for: Paint, App_Pythia and the module kit do not build | `base/pkgconfig/tomlplusplus.pc`, written for the installed version (`[base.pkgconfig]`), on `PKG_CONFIG_PATH` by `activate.sh` |
| ready-made ROOT | conda-forge builds it for C++20 and 23 only; at the stack's C++17, every source including it warns that the standards differ | a ready-made ROOT makes the stack C++20, and the base asks for that build (`conda_std`; `root_base * cxx20*`); a C++17 `cxx_std` set with it is refused |
| ready-made Pythia8 | its `pythia8-config --cxxflags` says `-std=c++11`, after the stack's own on the compile line | `framework/rules.mk` puts the stack's `-std` last |
| ready-made ROOT | its headers are in the base's `include/`, which every source sees, so `Module.hh` turns its ROOT output on in modules that do not link ROOT (`TVersionCheck` undefined) | `rules.mk`: a source using the kit links ROOT too when ROOT's headers are in the base |
| HepMC3 | `pyHepMC3` built but not installed; `GenEvent` missing from it | `-DHEPMC3_Python_SITEARCH<XY>=<venv site-packages>` (`HEPMC3_PYTHON_INSTALL_DIR` is ignored), and `-fno-lto`: LTO strips the pybind11 symbols |
| FastJet | several Rivets in one process (InprocJets, `rivet_threads`) cluster SISCone jets with one shared random state: other jets, or a FastJet internal error | `fastjet.patch`: `recipes/patches/fastjet-3.5.0-siscone-thread-local-ranlux.patch`, the state per thread; one thread draws exactly what it drew before |
| fjcontrib | `make install` gives only static contrib libraries | `make fragile-shared-install` as well: `libfastjetcontribfragile.so`, as the lab PC has it |
| ROOT | 6.40.00's `rootcling_stage1` fails to link (`clang::CodeGenerator::GetModule()`) | pinned to 6.40.04, which fixes that regression |
| ROOT | parallel compilation of its LLVM/Cling OOM-kills `cc1plus`, and the truncated objects then fail later links with errors that look unrelated | `root_cores`: one compiler per 1.3 GB of available memory (12 on an idle 16 GB); every other package at `cores` |
| ROOT | `-DPYTHON_EXECUTABLE`, `-Dglew`, `-Dpython3` are ignored by 6.40 | `-DPython3_EXECUTABLE=<venv>` (FindPython3), `-Dpyroot=ON` |
| ROOT | an external xrootd 6.x is untested against ROOT 6.40, and ROOT does not read `XROOTD_ROOT_DIR` | `-Dxrootd=ON -Dbuiltin_xrootd=ON`, `-Ddavix=OFF` |
| ROOT | the features the framework and the lab PC use | `mathmore roofit tmva fftw3 sqlite xml gdml http imt ssl vdt` on; `x11 opengl webgui asimage` follow `graphics` |
| Pythia8 | its Rivet and ROOT plugins exist only if it is built after them | after ROOT and Rivet; `optional` adds `--with-root --with-rivet` when they are there |
| Python | pip wheels of FastJet or HepMC3 do not match the stack's symbols | every compiled HEP library is built here; pip installs only pure-Python and ML packages |
