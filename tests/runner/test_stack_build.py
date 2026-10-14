"""recipes/build_stack.py: the stack's build, from recipes/toolkits/ and settings.toml. Only
plans and dry runs here (nothing is built or downloaded); every prefix is a tmp_path."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from runner import plugins
import functools
import gzip
import http.server
import io
import tarfile
import threading

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bs():
    return plugins.load(REPO / "recipes" / "build_stack.py", "build_stack")


def planned(bs, prefix, *args):
    _, s, packages = bs.options([f"machine={prefix}", *args])
    c = bs.context(s)
    return bs.plan(s, packages, c), packages, c


def test_core_and_all_follow_the_file(bs, tmp_path):
    (core, added), packages, _ = planned(bs, tmp_path)
    assert added == []
    assert core == [n for n, p in packages.items() if p.get("group") == "core"]
    assert core[0] == "python" and core[-1] == "pdfsets"
    (everything, _), _, _ = planned(bs, tmp_path, "packages=all")
    assert everything == [n for n, p in packages.items() if p.get("group") in ("core", "extra")]
    assert "evtgen" in packages and "evtgen" not in everything        # the toolkits' join only by name or @kit
    for name in everything:                                        # each after what it needs
        assert all(everything.index(need) < everything.index(name) for need in packages[name].get("needs", []))


def test_needs_are_added_only_when_missing(bs, tmp_path):
    (order, added), _, _ = planned(bs, tmp_path, "packages=rivet")
    assert order == ["python", "hepmc3", "yoda", "fastjet", "fjcontrib", "rivet"]
    assert added == order[:-1]
    stamps = tmp_path / "stack" / ".stamps"
    stamps.mkdir(parents=True)
    for name in ("python", "hepmc3-3.3.1", "yoda-2.1.4"):
        (stamps / name).touch()
    (tmp_path / "stack" / "fastjet" / "lib").mkdir(parents=True)    # FastJet installed otherwise: its dir
    (order, added), _, _ = planned(bs, tmp_path, "packages=rivet")
    assert order == ["fjcontrib", "rivet"]                         # fjcontrib's probe is its library


def test_overrides_reach_the_tarball_and_the_arguments(bs, tmp_path):
    (_, _), packages, c = planned(bs, tmp_path, "root.release=6.40.06", "graphics=OFF", "root.extra=-Da=1 -Db=2")
    file, url = bs.tarball("root", packages["root"], c)
    assert file.name == "root-6.40.06.tar.gz" and url.endswith("root_v6.40.06.source.tar.gz")
    k = bs.scope("root", packages["root"], c)
    args = bs.words(packages["root"]["args"], k)
    assert "-Dx11=OFF" in args and packages["root"]["extra"] == "-Da=1 -Db=2"
    k["names"] = ["a", "b"]
    assert bs.words(["-x", "{names}", "-y={names}"], k) == ["-x", "a", "b", "-y=a b"]   # a list's words
    _, s, packages = bs.options([f"machine={tmp_path}", "madgraph.release=3.6.2"])
    assert "/3.6.x/" in bs.tarball("madgraph", packages["madgraph"], bs.context(s))[1]   # {series}


@pytest.mark.parametrize("arg", ["corez=3", "root.relase=1", "nope.release=1", "bogus", "cores=abc",
                                 "packages=foo"])
def test_mistakes_are_refused(bs, tmp_path, arg):
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, arg)


def test_a_config_file_changes_and_adds_packages(bs, tmp_path):
    extra = tmp_path / "my.toml"
    extra.write_text('[settings]\ncores = 3\n[packages.root]\nrelease = "6.40.06"\n'
                     '[packages.mine]\nrelease = "1"\nurl = "https://x/mine-{release}.tgz"\nkind = "cmake"\nneeds = ["root"]\n')
    (order, added), packages, c = planned(bs, tmp_path, "--config", str(extra), "packages=mine", "cores=2")
    assert order == ["python", "root", "mine"] and added == ["python", "root"]
    assert c["cores"] == 2 and packages["root"]["release"] == "6.40.06"   # the command line wins over the file



def test_machine_toml_is_this_machines_layer(bs, tmp_path):
    """Audit 3, phase 3.1: lists append, unless the table says replace; scalars replace; the command line wins."""
    (tmp_path / "machine.toml").write_text(
        '[settings]\ncores = 7\nroot_cores = 2\npdf_sets = ["NNPDF31_nnlo_as_0118"]\nsetup_extra = ["module load x"]\n'
        '[env]\nFOO = "bar"\n'
        '[packages.root]\nargs = ["-Dmine=ON"]\n'
        '[packages.yoda]\nargs = ["--x"]\nreplace = ["args"]\n'
        '[packages.mine]\nrelease = "1"\nurl = "https://x/mine-{release}.tgz"\nkind = "cmake"\nneeds = ["root"]\n'
        '[cluster]\naccount = "lab"\n', encoding="utf-8")
    shipped = bs.read(REPO / "recipes" / "toolkits" / "standard.toml")["packages"]
    (order, _), packages, c = planned(bs, tmp_path, "packages=mine", "cores=3")
    assert c["cores"] == 3 and c["root_cores"] == 2                # the command line wins; the file's own stays
    assert c["pdf_sets"][-1] == "NNPDF31_nnlo_as_0118" and len(c["pdf_sets"]) > 1
    assert c["setup_extra"] == ["module load x"] and c["env"]["FOO"] == "bar" and "CXXFLAGS" in c["env"]
    assert packages["root"]["args"] == [*shipped["root"]["args"], "-Dmine=ON"]
    assert packages["yoda"]["args"] == ["--x"]
    assert order[-1] == "mine" and "machine.toml" in c["_layers"]


@pytest.mark.parametrize("text, message", [
    ('[setting]\ncores = 1\n', r"no table \[setting\]"),
    ('[settings]\nmachine = "/x"\n', "no key 'machine'"),
    ('[settings]\nkores = 1\n', "no key 'kores'"),
    ('[packages.root]\nrelease_ = "1"\n', "no key 'release_'"),
    ('[packages.root]\nreplace = "extra"\n', "replace is a list"),
])
def test_machine_toml_is_checked(bs, tmp_path, text, message):
    (tmp_path / "machine.toml").write_text(text, encoding="utf-8")
    with pytest.raises(SystemExit, match=message):
        bs.options([f"machine={tmp_path}"])


def test_the_templates_examples_are_the_tables_the_build_reads(bs, tmp_path):
    """recipes/machine.template.toml, a new root's machine.toml: all commented out; uncommented, it reads."""
    import tomllib
    template = (REPO / "recipes" / "machine.template.toml").read_text(encoding="utf-8")
    assert all(line.startswith("#") for line in template.splitlines() if line.strip())
    examples = template.split("\n\n", 1)[1]                          # after the header
    text = "\n".join(line[2:] if line.startswith("# ") else line for line in examples.splitlines())
    assert list(tomllib.loads(text)) == list(bs.MACHINE_TABLES)
    (tmp_path / "machine.toml").write_text(text, encoding="utf-8")
    _, s, packages = bs.options([f"machine={tmp_path}"])
    assert s["cores"] == 20 and packages["root"]["extra"][-1] == "-Dcuda=ON"

def test_the_dry_run_is_a_bash_script_and_writes_nothing(bs, tmp_path, capsys):
    """The default: the conda base first (pixi fetched and checked, the manifest, `pixi install`, the
    activation), then every build inside it (docs/conda/)."""
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=all", "root_cores=2"])
    script = capsys.readouterr().out
    assert not prefix.exists()
    assert script.isascii()                                         # any locale can print and save it
    assert subprocess.run(["bash", "-n"], input=script, text=True).returncode == 0
    env = prefix / "base" / ".pixi" / "envs" / "default"
    for line in ("set -euo pipefail", "-p0 -i " + str(REPO / "recipes/patches"), "--with-hepmcversion=3",
                 "make fragile-shared-install", f"cmake --build {prefix}/forge/build/root -j2",
                 f"{prefix}/forge/downloads/pixi-0.81.0-", "sha256sum -c -", f"cat > {prefix}/base/pixi.toml <<'EOF'",
                 f"{prefix}/forge/pixi/bin/pixi install --manifest-path {prefix}/base/pixi.toml",
                 f"source {prefix}/base/activate.sh", f"{env}/bin/python {REPO}/recipes/pth.py",
                 f"-DPython3_EXECUTABLE={env}/bin/python", f"--with-zlib={env}", f"export LDFLAGS='-L{env}/lib -Wl,-rpath,{env}/lib",
                 f"--with-root={prefix}/stack/root", "lhapdf install CT14lo CT14nlo", f"{prefix}/forge/downloads/root-6.40.04.tar.gz"):
        assert line in script, line
    assert "apt-get" not in script and "-m venv" not in script and "unset VIRTUAL_ENV" in script
    assert script.index("pixi install") < script.index("source ") < script.index("# == python")
    assert "setup.sh <<" not in script and "machine.sh" not in script   # setup.sh is tracked; no extra lines on Linux
    assert script.index("# == root") < script.index("# == pythia8")


def test_the_old_way_is_apt_and_a_venv(bs, tmp_path, capsys):
    """base=system: apt_packages and a venv, as before the base."""
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=all", "base=system", "root_cores=2"])
    script = capsys.readouterr().out
    for line in (f"-m venv --prompt HEP {prefix}/venv", f"{prefix}/venv/bin/python {REPO}/recipes/pth.py",
                 "apt-get install", f"--with-root={prefix}/stack/root", f"-DPython3_EXECUTABLE={prefix}/venv/bin/python"):
        assert line in script, line
    assert "pixi" not in script and "-isystem" not in script and "--with-zlib" not in script


def test_a_machine_root_made_before_the_base_stays_on_the_system(bs, tmp_path):
    """Nothing is converted (the user, 2026-10-14): a root with a venv/ and no base/ builds as it did,
    unless base= says otherwise; a new root gets the base."""
    (tmp_path / "old" / "venv").mkdir(parents=True)
    assert bs.options([f"machine={tmp_path / 'old'}"])[1]["base"] == "system"
    assert bs.options([f"machine={tmp_path / 'old'}", "base=conda"])[1]["base"] == "conda"
    assert bs.options([f"machine={tmp_path / 'new'}"])[1]["base"] == "conda"
    with pytest.raises(SystemExit, match="base is"):
        bs.options([f"machine={tmp_path}", "base=brew"])


def test_the_mac_overlay(bs, tmp_path, monkeypatch, capsys):
    """recipes/platforms/mac/mac.toml, laid by itself with macOS switched on, and system.toml with
    base=system: no apt, Homebrew's paths, ROOT through Cocoa, absolute install names, DYLD_LIBRARY_PATH,
    the macOS ONNX Runtime."""
    monkeypatch.setattr(bs, "MAC", True)
    monkeypatch.setenv("HOMEBREW_PREFIX", "/opt/homebrew")
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=all", "base=system"])
    script = capsys.readouterr().out
    root = next(line for line in script.splitlines() if line.startswith(f"cmake -S {prefix}/forge/src/root "))
    assert root.index("-Dx11=OFF") < root.index("-Dcocoa=ON")        # the overlay's come last, and win
    assert "-DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3" in root
    assert f"-DCMAKE_INSTALL_NAME_DIR={prefix}/stack/hepmc3/lib" in script
    assert "-DCMAKE_INSTALL_NAME_DIR" not in next(line for line in script.splitlines()
                                                  if line.startswith(f"cmake -S {prefix}/forge/src/sherpa "))
    for line in ("export DYLD_LIBRARY_PATH=", "export CPPFLAGS=-I/opt/homebrew/include", "onnxruntime-osx-",
                 "sed -i.orig", "export DYLD_LIBRARY_PATH=$LD_LIBRARY_PATH",
                 "PATH=/opt/homebrew/opt/$_g/libexec/gnubin:$PATH", f"cat > {prefix}/machine.sh"):
        assert line in script, line
    assert "apt-get" not in script and "export LD_LIBRARY_PATH=" not in script
    assert subprocess.run(["bash", "-n"], input=script, text=True, encoding="utf-8").returncode == 0


def test_the_mac_on_the_conda_base_needs_no_homebrew(bs, tmp_path, monkeypatch, capsys):
    """mac.toml and conda.toml: no {HOMEBREW_PREFIX} anywhere (it is not set), the base's GSL and rpath."""
    monkeypatch.setattr(bs, "MAC", True)
    monkeypatch.delenv("HOMEBREW_PREFIX", raising=False)
    monkeypatch.setattr(bs.os, "uname", lambda: type("U", (), {"sysname": "Darwin", "machine": "arm64"})())
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=@primary"])
    script = capsys.readouterr().out
    env = prefix / "base" / ".pixi" / "envs" / "default"
    thepeg = next(line for line in script.splitlines() if "./configure" in line and "/thepeg " in line)
    assert f"--with-gsl={env}" in thepeg and f"'LDFLAGS=-L{env}/lib -Wl,-rpath,{env}/lib -lc++'" in thepeg
    assert "homebrew" not in script.lower() and "-rpath-link" not in script and "aarch64-apple-darwin" in script
    assert 'platforms = ["osx-arm64"]' in script and "clangxx_osx-arm64" in script and "gcc_linux-64" not in script


def test_the_system_packages_carry_what_decks_need(bs, tmp_path):
    """hep deck (docs/reporter): pandoc for the slides, poppler for a figure's PNG, the Beamer class."""
    _, s, _ = bs.options([f"machine={tmp_path}"])
    assert {"pandoc", "poppler-utils", "texlive-latex-recommended"} <= set(s["apt_packages"])


# ── toolkits (recipes/toolkits/, README.md §6) ─────────────────────────────────────────────────

def test_every_toolkit_plans_and_names_only_packages(bs, tmp_path):
    _, _, packages = bs.options([f"machine={tmp_path}"])
    kits = bs.kit_files(tmp_path)
    assert {"standard", "lab", "bsm-recast", "heavy-flavour", "detector", "key4hep"} <= set(kits)
    for name in kits:
        (order, _), _, _ = planned(bs, tmp_path, f"packages=@{name}")
        assert order or name == "conda", name                       # @conda is a layer: it adds no package
        for package in order:                                        # each after what it needs
            assert all(order.index(n) < order.index(package) for n in packages[package].get("needs", []) if n in order)
    (lab, _), _, _ = planned(bs, tmp_path, "packages=@lab")
    (everything, _), _, _ = planned(bs, tmp_path, "packages=all")
    assert lab == everything and "hdf5" in lab                       # HDF5 in the lab set (the user's decision)
    (primary, _), _, _ = planned(bs, tmp_path, "packages=@primary")
    assert primary == everything + ["madanalysis5"]                  # the primary workflow: ~/HEP's and MadAnalysis 5
    (standard, _), _, _ = planned(bs, tmp_path, "packages=@standard")
    (core, _), _, _ = planned(bs, tmp_path, "packages=core")
    assert standard == core


def test_the_recipes_are_one_file_and_each_toolkit_one_more(bs):
    """Audit 3, phase 3.2: standard.toml holds every recipe; the other files hold no recipe of their own."""
    standard = bs.read(REPO / "recipes" / "toolkits" / "standard.toml")
    assert len(standard["packages"]) >= 48 and standard["standard"] == {"core": True}
    for file in (REPO / "recipes" / "toolkits").glob("*.toml"):
        data = bs.read(file)
        assert set(data) <= bs.KIT_FIELDS, file.name
        if file.name != "standard.toml":
            assert set(data.get("packages", {})) <= set(standard["packages"]), file.name
    for name in ("heavy-ion", "data"):                               # HDF5 named where the user asked
        assert bs.read(REPO / "recipes" / "toolkits" / f"{name}.toml")["standard"]["hdf5"] is True
    assert not (REPO / "recipes" / "packages.toml").exists() and not (REPO / "recipes" / "toolkits.toml").exists()


def test_the_shells_package_list_is_the_recipes(bs):
    """env/packages.sh is generated from the recipes (make registry), so the shell's list cannot drift."""
    assert (REPO / "env" / "packages.sh").read_text(encoding="utf-8") == bs.packages_sh(), "run: make registry"
    text = bs.packages_sh()
    for folder in ("LHAPDF", "herwig7", "hdf5", "podio", "adept"):   # the isolated stacks' too
        assert f" {folder}" in text or f'"{folder}' in text
    assert "xrootd" not in text and "pdfsets" not in text


def test_every_stack_toml_library_is_a_recipe_or_the_systems(bs):
    """env/stack.toml stays written by hand (its hash keys flags.mk: an edit rebuilds every app and module);
    each of its entries is a recipe's library, or one the system provides."""
    import tomllib
    stack = tomllib.loads((REPO / "env" / "stack.toml").read_text(encoding="utf-8"))
    recipes = bs.read(REPO / "recipes" / "toolkits" / "standard.toml")["packages"]
    system = {"toml": "libtomlplusplus-dev", "zstd": "libzstd-dev", "zlib": "zlib1g-dev"}
    conda = {"toml": "tomlplusplus", "zstd": "zstd", "zlib": "zlib"}             # the same, in the base
    base = {e for group in bs.read(bs.BASE_FILE)["base"]["libraries"].values() for e in group}
    named = {"onnx": "onnxruntime"}
    for entry in stack:
        if entry in system:
            assert system[entry] in bs.read(REPO / "recipes" / "settings.toml")["apt_packages"], entry
            assert conda[entry] in base, entry
        else:
            assert named.get(entry, entry) in recipes, entry


def test_a_toolkit_brings_what_it_needs(bs, tmp_path):
    (order, added), _, _ = planned(bs, tmp_path, "packages=@heavy-flavour")
    assert order[-3:] == ["photospp", "tauolapp", "evtgen"]              # PHOTOS++ and TAUOLA++ before EvtGen
    assert "photospp" in added and "tauolapp" in added
    (mixed, _), _, _ = planned(bs, tmp_path, "packages=@data rivet")     # toolkits and names together
    assert {"highfive", "hepdata", "rivet", "hdf5"} <= set(mixed)
    (ions, _), _, _ = planned(bs, tmp_path, "packages=@heavy-ion")
    assert ions.index("hdf5") < ions.index("yoda")                       # YODA after HDF5: .yoda.h5


@pytest.mark.parametrize("arg", ["packages=@nope", "packages=@"])
def test_an_unknown_toolkit_is_refused(bs, tmp_path, arg):
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, arg)


def test_external_packages_are_never_built(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=@key4hep @cms @fluka", "base=system", "system=false"])
    out = capsys.readouterr()
    assert "# == key4hep" not in out.out and "curl" not in out.out   # nothing fetched, nothing run
    for name in ("key4hep", "cmssw", "fluka"):
        assert f"{name}: external" in out.err, name
    _, _, packages = bs.options([f"machine={tmp_path}"])
    assert all(p.get("how") for p in packages.values() if p["kind"] == "external")


def test_new_recipes_say_so_and_bring_their_system_packages(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=@detector", "base=system"])
    out = capsys.readouterr()
    assert "dd4hep 01-38  (a recipe not yet proven by a build)" in out.err
    install = next(line for line in out.out.splitlines() if "apt-get install" in line)
    assert "libeigen3-dev" in install and "nlohmann-json3-dev" in install and "libxerces-c-dev" in install
    bs.main(["--dry-run", f"machine={prefix}", "packages=@detector"])           # the base: conda-forge's names
    manifest = capsys.readouterr().out
    assert 'eigen = "*"' in manifest and 'nlohmann_json = "*"' in manifest and 'xerces-c = "*"' in manifest
    _, _, packages = bs.options([f"machine={tmp_path}"])
    proven = [n for n, p in packages.items() if p.get("group") in ("core", "extra")]
    assert not [n for n in proven if packages[n].get("status")]          # the lab PC's recipes are proven


# ── isolated toolkits, and a machine's own (<machine root>/toolkits/) ──────────────────────────

def test_an_isolated_toolkit_builds_a_stack_of_its_own(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=@key4hep-src"])
    script = capsys.readouterr().out
    base = prefix / "stacks" / "key4hep-src"
    root = next(line for line in script.splitlines() if line.startswith(f"cmake -S {prefix}/forge/src/root "))  # forge/src/ is shared
    assert f"-DCMAKE_INSTALL_PREFIX={base}/stack/root" in root and "-DCMAKE_CXX_STANDARD=20" in root
    assert f"pixi install --manifest-path {base}/base/pixi.toml" in script      # a base of its own
    assert f"{prefix}/forge/pixi/bin/pixi" in script                            # one pixi per machine
    assert "-DGEANT4_BUILD_CXXSTD=20" in script                     # the toolkit's [packages.geant4]
    assert f"cat > {base}/setup.sh" in script and "HEP_STACK_REQUEST=key4hep-src" in script
    assert f"{prefix}/stack/" not in script                           # the default stack is not touched


def test_the_default_stack_keeps_cxx17(bs, tmp_path):
    (_, _), _, c = planned(bs, tmp_path, "packages=@detector")
    assert c["cxx_std"] == 17 and c["stack"] == "" and c["inst"] == str(tmp_path.resolve() / "stack")


def write_kit(root, name, text):
    (root / "toolkits").mkdir(parents=True, exist_ok=True)
    (root / "toolkits" / f"{name}.toml").write_text(text, encoding="utf-8")


def test_a_machines_toolkit_extends_one_takes_one_out_and_adds_a_recipe(bs, tmp_path, capsys):
    """06_Plan 3.2's row: <machine>/toolkits/mine.toml, extends = "lab", one package off, one recipe added."""
    write_kit(tmp_path, "mine", 'description = "mine"\nextends = "lab"\n[standard]\nsherpa = false\n'
              '[packages.rivet]\nrelease = "4.1.4"\n'
              '[packages.mygen]\nrelease = "1.2"\nurl = "https://example.org/mygen-{release}.tar.gz"\n'
              'kind = "cmake"\nneeds = ["hepmc3"]\n')
    before = sorted(p.relative_to(REPO) for p in (REPO / "recipes").rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    (order, _), packages, _ = planned(bs, tmp_path, "packages=@mine")
    (lab, _), _, _ = planned(bs, tmp_path, "packages=@lab")
    assert "sherpa" not in order and order[-1] == "mygen" and set(order) == set(lab) - {"sherpa"} | {"mygen"}
    assert packages["rivet"]["release"] == "4.1.4"
    bs.main(["--list", "@mine", f"machine={tmp_path}"])
    out = capsys.readouterr().out
    assert "@lab: all" in out and "@mine: its recipe" in out and "release ← @mine" in out
    bs.main(["--toolkits", f"machine={tmp_path}"])
    assert f"this machine's ({tmp_path / 'toolkits' / 'mine.toml'})" in capsys.readouterr().out
    after = sorted(p.relative_to(REPO) for p in (REPO / "recipes").rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    assert before == after                                             # Heimdall's tree untouched


def test_a_machines_toolkit_of_a_shipped_name_is_used_and_may_extend_it(bs, tmp_path, capsys):
    write_kit(tmp_path, "lab", 'description = "the lab, without ONNX"\nextends = "lab"\n[standard]\nonnxruntime = false\n')
    (order, _), _, _ = planned(bs, tmp_path, "packages=@lab")
    (everything, _), _, _ = planned(bs, tmp_path, "packages=all")
    assert order == [n for n in everything if n != "onnxruntime"]
    bs.main(["--toolkits", f"machine={tmp_path}"])
    assert "over Heimdall's" in capsys.readouterr().out


@pytest.mark.parametrize("name, text, message", [
    ("mine", '[standard]\ncore = true\n[settings]\ncxx_std = 20\n', "must be isolated"),
    ("mine", 'colour = "red"\n', "no key colour"),
    ("mine", '[standard]\nnope = true\n', "no group or package 'nope'"),
    ("mine", '[standard]\ncore = "yes"\n', "true or false"),
    ("mine", 'extends = "mine2"\n', "no toolkit 'mine2'"),
    ("mine", '[packages.rivet]\nrelaese = "1"\n', "no key 'relaese'"),
    ("mine", '[settings]\npackages = "all"\n', "no key 'packages'"),
    ("standard", '[standard]\ncore = true\n', "@standard is Heimdall's recipes"),
])
def test_a_bad_toolkit_is_refused(bs, tmp_path, name, text, message):
    write_kit(tmp_path, name, text)
    with pytest.raises(SystemExit, match=message):
        planned(bs, tmp_path, f"packages=@{name}")


def test_toolkits_that_go_round_are_refused(bs, tmp_path):
    write_kit(tmp_path, "a", 'extends = "b"\n')
    write_kit(tmp_path, "b", 'extends = "a"\n')
    with pytest.raises(SystemExit, match="go round"):
        planned(bs, tmp_path, "packages=@a")


def test_extending_an_isolated_toolkit_is_isolated(bs, tmp_path):
    write_kit(tmp_path, "gpu-mine", 'extends = "gpu-sim"\n[standard]\ng4hepem = true\n')
    (_, _), _, c = planned(bs, tmp_path, "packages=@gpu-mine")
    assert c["stack"] == "gpu-mine" and c["cxx_std"] == 20


def test_one_isolated_stack_per_run(bs, tmp_path):
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, "packages=@key4hep-src @gpu-sim")
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, "_stack=sneaky")                       # the internal key is not a setting


# ── downloads (phase 1.1 of docs/audit_3/06_Plan.md) ───────────────────────────────────────────

def a_tarball() -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
        data = b"x" * 200_000
        info = tarfile.TarInfo("pkg-1/big.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return raw.getvalue()


@pytest.fixture
def server():
    """A local web server: /good.tgz an archive, /page.tgz a web page with status 200, /short.tgz an
    archive cut off after a third (its Content-Length says the whole), /ranged.tgz honours Range."""
    body = a_tarball()
    hits: dict[str, int] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits[self.path] = hits.get(self.path, 0) + 1
            if self.path == "/good.tgz":
                self._send(200, body)
            elif self.path == "/page.tgz":
                self._send(200, b"<!DOCTYPE html><html>no such release</html>")
            elif self.path == "/short.tgz":
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body[: len(body) // 3])
            elif self.path == "/ranged.tgz":
                start = int(self.headers.get("Range", "bytes=0-").split("=")[1].rstrip("-") or 0)
                if hits[self.path] == 1:                              # the first answer stops half-way
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body[: len(body) // 2])
                else:
                    self._send(206 if start else 200, body[start:])
            else:
                self._send(404, b"not here")

        def _send(self, code, data):
            self.send_response(code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", body, hits
    httpd.shutdown()


def test_a_web_page_and_a_cut_off_file_are_not_archives(bs, tmp_path):
    page, short, good = tmp_path / "page.tgz", tmp_path / "short.tgz", tmp_path / "good.tgz"
    page.write_bytes(b"<!DOCTYPE html><html></html>")
    body = a_tarball()
    short.write_bytes(body[: len(body) // 3])
    good.write_bytes(body)
    assert "web page" in bs.archive_problem(page)
    assert "cut off" in bs.archive_problem(short)
    assert bs.archive_problem(good) is None
    assert "sha256 differs" in bs.archive_problem(good, "0" * 64)
    assert bs.archive_problem(good, bs.sha256_of(good)) is None


def test_downloads_try_mirrors_refuse_pages_and_resume(bs, tmp_path, server, monkeypatch):
    base, body, hits = server
    monkeypatch.setattr(bs, "BACKOFF", 0)
    shell = bs.Shell(False, {})
    first = tmp_path / "a.tgz"
    bs.fetch([(first, [f"{base}/page.tgz", f"{base}/missing.tgz", f"{base}/good.tgz"], "")], shell)
    assert first.read_bytes() == body                                # the page refused, the 404 skipped, the mirror taken
    resumed = tmp_path / "b.tgz"
    bs.fetch([(resumed, [f"{base}/ranged.tgz"], "")], shell)
    assert resumed.read_bytes() == body and hits["/ranged.tgz"] == 2   # the second request resumed the first
    with pytest.raises(SystemExit) as stop:
        bs.fetch([(tmp_path / "c.tgz", [f"{base}/page.tgz"], "")], shell)
    assert not (tmp_path / "c.tgz").exists()
    damaged = tmp_path / "d.tgz"                                     # an archive left cut off by an earlier run
    damaged.write_bytes(body[:1000])
    bs.fetch([(damaged, [f"{base}/good.tgz"], "")], shell)
    assert damaged.read_bytes() == body


def test_a_short_answer_is_retried_then_refused(bs, tmp_path, server, monkeypatch):
    base, _, hits = server
    monkeypatch.setattr(bs, "BACKOFF", 0)
    assert "IncompleteRead" in bs.download(tmp_path / "s.tgz", f"{base}/short.tgz")
    assert hits["/short.tgz"] == bs.ATTEMPTS


def test_the_dry_run_prints_the_whole_build_unless_resumed(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    stamps = prefix / "stack" / ".stamps"
    stamps.mkdir(parents=True)
    (stamps / "hepmc3-3.3.1").touch()
    bs.main(["--dry-run", f"machine={prefix}", "packages=rivet", "system=false"])
    whole = capsys.readouterr().out
    assert "# == hepmc3" in whole and "--retry-all-errors" in whole and "-C -" in whole
    assert "cedar-tools.web.cern.ch/downloads/Rivet-4.1.4.tar.gz" in whole and "yoda.hepforge.org" in whole
    bs.main(["--dry-run", "--resume", f"machine={prefix}", "packages=rivet", "system=false"])
    assert "# == hepmc3" not in capsys.readouterr().out


def test_pythia_and_rivet_come_from_where_they_live_now(bs, tmp_path):
    _, s, packages = bs.options([f"machine={tmp_path}"])
    c = bs.context(s)
    assert bs.urls_of("pythia8", packages["pythia8"], c)[0].startswith("https://pythia.org/releases/pythia83/")
    assert bs.urls_of("rivet", packages["rivet"], c)[0].startswith("https://cedar-tools.web.cern.ch/")
    assert "pdfsets" in packages["whizard"]["needs"]                 # its LHAPDF needs CT10 and cteq6l1 first


# ── a clean build environment, the preflight, explicit options (phase 1.2) ─────────────────────

def test_the_build_leaves_another_stack_out(bs, tmp_path, monkeypatch):
    other = tmp_path / "old" / "bin"
    other.mkdir(parents=True)
    (other / "root-config").touch()
    monkeypatch.setenv("PATH", f"{other}:/usr/bin:/bin")
    monkeypatch.setenv("ROOTSYS", str(tmp_path / "old"))
    monkeypatch.setenv("LD_LIBRARY_PATH", str(tmp_path / "old" / "lib"))
    monkeypatch.setenv("LC_ALL", "C")
    (_, _), _, c = planned(bs, tmp_path)
    env, dropped = bs.clean_environment(c)
    assert "ROOTSYS" not in env and "LD_LIBRARY_PATH" not in env and env["LC_ALL"] == "C"
    assert env["PATH"] == "/usr/bin:/bin"
    assert "ROOTSYS" in dropped and f"PATH:{other}" in dropped


def test_a_mac_build_goes_through_build_sh(bs, tmp_path, monkeypatch):
    """On macOS the platform's fixes are laid by themselves; Homebrew and the GNU tools are build.sh's."""
    monkeypatch.setattr(bs, "MAC", True)
    monkeypatch.setenv("HOMEBREW_PREFIX", "/opt/homebrew")
    monkeypatch.delenv("HEP_BUILD_SH", raising=False)
    _, s, packages = bs.options([f"machine={tmp_path}"])
    assert "platform mac" in s["_layers"] and "-Dcocoa=ON" in packages["root"]["extra"]
    with pytest.raises(SystemExit) as stop:
        bs.preflight(s, bs.context(s), [])
    assert "recipes/platforms/mac/build.sh" in str(stop.value)
    monkeypatch.setenv("HEP_BUILD_SH", "1")
    monkeypatch.setattr(bs.shutil, "which", lambda name: None if name == "brew" else "/usr/bin/" + name)
    bs.preflight(s, bs.context(s), [])                              # through build.sh: no stop


def test_a_platform_is_laid_only_where_it_is(bs, tmp_path):
    _, s, packages = bs.options([f"machine={tmp_path}"])
    assert "platform mac" not in s.get("_layers", []) and "extra" not in packages["root"]
    with pytest.raises(SystemExit, match="no platform 'nope'"):
        bs.options(["--platform", "nope", f"machine={tmp_path}"])


def test_yoda_takes_hdf5_only_from_the_stack(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=yoda", "system=false"])
    alone = next(line for line in capsys.readouterr().out.splitlines() if "./configure" in line and "/yoda " in line)
    assert "--disable-h5" in alone and "--enable-h5" not in alone
    bs.main(["--dry-run", f"machine={prefix}", "packages=yoda hdf5", "system=false"])
    script = capsys.readouterr().out
    assert script.index("# == hdf5") < script.index("# == yoda")    # the optional one first
    yoda = next(line for line in script.splitlines() if "./configure" in line and "/yoda " in line)
    assert yoda.index("--disable-h5") < yoda.index("--enable-h5")   # the later wins
    assert f"--with-hdf5={prefix}/stack/hdf5/bin/h5cc-plain" in yoda
    assert "hdf5-2.2.0.tar.gz -C" in script and "--strip-components=2" in script
    assert "recipes/helpers/h5cc_plain.py" in script


def test_h5cc_plain_answers_in_one_line_each(tmp_path):
    install = tmp_path / "hdf5"
    (install / "bin").mkdir(parents=True)
    subprocess.run(["python3", str(REPO / "recipes/helpers/h5cc_plain.py"), str(install), "2.2.0"], check=True,
                   capture_output=True)
    show = subprocess.run([str(install / "bin/h5cc-plain"), "-showconfig"], capture_output=True, text=True).stdout
    assert show.splitlines() == ["HDF5 Version: 2.2.0", f"Installation point: {install}", "Extra libraries: -lz"]
    assert subprocess.run([str(install / "bin/h5cc-plain"), "-show"], capture_output=True, text=True).stdout.strip() \
        == f"cc -I{install}/include -L{install}/lib -lhdf5"


# ── stamps, rebuilds, overrides, the ABI guard, the Mac's fixes (phase 1.3) ────────────────────

def stamped(bs, prefix, name, content=None, packages=None, c=None):
    _, s, packages = bs.options([f"machine={prefix}"]) if packages is None else (None, None, packages)
    c = c or bs.context(s)
    file = bs.stamp(name, packages[name], c)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(bs.digest(name, packages[name], c) if content is None else content, encoding="utf-8")
    return packages, c


def test_a_stamp_knows_the_recipe_it_was_built_with(bs, tmp_path):
    packages, c = stamped(bs, tmp_path, "fastjet")
    assert bs.state("fastjet", packages["fastjet"], c) == "built"
    packages["fastjet"]["args"] = [*packages["fastjet"]["args"], "--enable-extra"]
    assert bs.state("fastjet", packages["fastjet"], c) == "changed"
    stamped(bs, tmp_path, "hepmc3", content="", packages=packages, c=c)
    assert bs.state("hepmc3", packages["hepmc3"], c) == "built (no digest)"
    bs.building("root", packages["root"], c).touch()
    assert bs.state("root", packages["root"], c) == "failed" and not bs.present("root", packages["root"], c)
    (Path(c["inst"]) / "yoda").mkdir()
    assert bs.state("yoda", packages["yoda"], c) == "installed"


def test_installed_is_used_failed_is_built_again(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    _, s, packages = bs.options([f"machine={prefix}"])
    c = bs.context(s)
    (Path(c["inst"]) / "fastjet").mkdir(parents=True)                # installed some other way: used
    stamped(bs, prefix, "hepmc3", packages=packages, c=c)
    bs.building("python", packages["python"], c).touch()             # an attempt that did not finish
    bs.main(["--dry-run", "--resume", f"machine={prefix}", "packages=fastjet hepmc3 python", "system=false"])
    script = capsys.readouterr().out
    assert "# == fastjet" not in script and "# == hepmc3" not in script and "# == python" in script


def test_rebuild_takes_what_depends_on_it(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    _, s, packages = bs.options([f"machine={prefix}"])
    c = bs.context(s)
    for name in ("python", "lhapdf", "hepmc3", "fastjet", "thepeg", "herwig", "rivet"):
        stamped(bs, prefix, name, packages=packages, c=c)
    assert bs.rebuild_set(["thepeg"], packages, c) == ["thepeg", "herwig"]
    bs.main(["--dry-run", "--resume", "--rebuild", "thepeg", f"machine={prefix}", "system=false"])
    script = capsys.readouterr().out
    assert "# == thepeg" in script and "# == herwig" in script and "# == rivet" not in script
    with pytest.raises(SystemExit):
        bs.main(["--dry-run", "--rebuild", "nope", f"machine={prefix}"])


def test_overrides_append_and_reach_the_environment(bs, tmp_path, monkeypatch):
    monkeypatch.setenv("HOMEBREW_PREFIX", "/opt/homebrew")
    _, s, packages = bs.options(["--platform", "mac", f"machine={tmp_path}",
                                 "root.extra+=-Dfoo=ON", "thepeg.extra+='LDFLAGS=-L/x -lc++'",
                                 "delphes.env.EXTRA=1", "env.MY_FLAG=yes", "pdf_sets=CT10,cteq6l1"])
    assert packages["root"]["extra"][-1] == "-Dfoo=ON" and "-Dcocoa=ON" in packages["root"]["extra"]
    assert packages["thepeg"]["extra"][-1] == "LDFLAGS=-L/x -lc++"
    assert packages["delphes"]["env"] == {"PYTHIA8": "{dir_pythia8}", "EXTRA": "1"}
    assert s["env"]["MY_FLAG"] == "yes" and s["pdf_sets"] == ["CT10", "cteq6l1"]


def test_another_cxx_standard_on_a_built_stack_is_refused(bs, tmp_path):
    prefix = tmp_path / "hep"
    stamps = prefix / "stack" / ".stamps"
    stamps.mkdir(parents=True)
    (stamps / "cxx_std").write_text("17\n")
    with pytest.raises(SystemExit) as stop:
        bs.main([f"machine={prefix}", "cxx_std=20", "system=false", "packages=fastjet"])
    assert "would mix ABIs" in str(stop.value)


def test_the_macs_fixes_are_recipe_lines(bs, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bs, "MAC", True)
    monkeypatch.setenv("HOMEBREW_PREFIX", "/opt/homebrew")
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=@primary", "base=system"])
    lines = capsys.readouterr().out.splitlines()
    thepeg = next(line for line in lines if "./configure" in line and "/thepeg " in line)
    for part in ("THEPEG_DYNAMIC_TYPE_INFO_BUG", "_LIBCPP_ENABLE_CXX17_REMOVED_BINDERS", "--with-gsl=/opt/homebrew/opt/gsl",
                 "'LDFLAGS=-L/opt/homebrew/lib -lc++'"):
        assert part in thepeg, part
    herwig = next(line for line in lines if "./configure" in line and "/herwig " in line)
    assert "-fdefault-integer-8" in herwig and "THEPEG_DYNAMIC_TYPE_INFO_BUG" in herwig
    whizard = next(line for line in lines if "./configure" in line and "/whizard " in line)
    assert "CXXLIBS=-lc++" in whizard


def test_a_failure_shows_its_errors_first(bs, tmp_path):
    log = tmp_path / "x.log"
    log.write_text("\n".join(["checking things", *(f"warning: noise {i}" for i in range(200)),
                               "../include/ThePEG/Repository/RandomGenerator.h:15:10: fatal error: 'gsl/gsl_rng.h' file not found",
                               *(f"warning: more noise {i}" for i in range(50)), "make: *** [Makefile:444: all-recursive] Error 1"]))
    excerpt = bs.failure_excerpt(log)
    assert excerpt.startswith("the first errors:") and "gsl/gsl_rng.h" in excerpt
    assert excerpt.index("gsl/gsl_rng.h") < excerpt.index("the log's end:")


# ── after an OS upgrade (phase 2.3) ────────────────────────────────────────────────────────────

def test_rebuild_broken_takes_what_lost_a_library_and_what_needs_it(bs, tmp_path, monkeypatch, capsys):
    prefix = tmp_path / "hep"
    _, s, packages = bs.options([f"machine={prefix}"])
    c = bs.context(s)
    for name in ("python", "lhapdf", "hepmc3", "fastjet", "root", "delphes", "rivet"):
        stamped(bs, prefix, name, packages=packages, c=c)
        (Path(c["inst"]) / packages[name].get("install", name)).mkdir(parents=True, exist_ok=True)

    class Scan:
        def problems(self, name, entries):
            return []

        def scan(self, folder):
            return (3, ["libgsl.so.27 (libMathMore.so)"]) if folder.name == "root" else (3, [])

    monkeypatch.setattr(bs, "checker", lambda: Scan())
    assert bs.broken(packages, c) == {"root": ["libgsl.so.27 (libMathMore.so)"]}
    bs.main(["--dry-run", "--resume", "--rebuild-broken", f"machine={prefix}", "system=false"])
    out = capsys.readouterr()
    assert "root: needs libgsl.so.27" in out.err
    assert "# == root" in out.out and "# == delphes" in out.out and "# == rivet" not in out.out


# ── the conda base (docs/conda/) ───────────────────────────────────────────────────────────────

def a_base(c, **installed):
    """A base as pixi leaves it, for the tests: conda-meta/<name>-<version>-<build>.json for each."""
    meta = Path(c["base"]) / "conda-meta"
    meta.mkdir(parents=True, exist_ok=True)
    for file in meta.glob("*.json"):
        file.unlink()
    for name, version in installed.items():
        (meta / f"{name.replace('_', '-') if name in ('lz4_c', 'fastjet_cxx') else name}-{version}-h0_0.json").write_text("{}")


def test_the_manifest_is_the_base_list_the_python_packages_and_the_runs_recipes(bs, tmp_path):
    (order, _), packages, c = planned(bs, tmp_path, "packages=@tuning", "base_packages=scipy 'gsl 2.8.*'",
                                      "python_packages+=pandas")
    text = bs.manifest_text(order, packages, c)
    import tomllib
    manifest = tomllib.loads(text)
    deps = manifest["dependencies"]
    assert manifest["workspace"]["channels"] == ["conda-forge"] and manifest["workspace"]["platforms"] == [c["conda_platform"]]
    assert list(deps)[0] == "python" and deps["python"] == "3.12.*"
    assert deps["gxx_linux-64"] == "15.*" and deps["sysroot_linux-64"] == "*"    # this platform's compilers;
    # the sysroot the newest the solve allows: a ready-made ROOT pins 2.17
    assert deps["tomli-w"] == "*" and deps["matplotlib-base"] == "*" and deps["pandas"] == "*"   # conda-forge's names
    assert deps["eigen"] == "*"                                                # professor's own (`base`)
    assert deps["scipy"] == "*" and deps["gsl"] == "2.8.*"                     # base_packages; a spec wins over "*"
    assert "clangxx_osx-arm64" not in deps and "rivet" not in deps            # rivet is built here
    assert text.isascii() and text.startswith("# base/pixi.toml")


def test_a_conda_toolkit_takes_what_conda_forge_carries_ready_made(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"machine={prefix}", "packages=@lab-conda"])
    out = capsys.readouterr()
    import tomllib
    deps = tomllib.loads(out.out.split("pixi.toml <<'EOF'\n")[1].split("EOF\n")[0])["dependencies"]
    for name in ("root", "rivet", "yoda", "hepmc3", "lhapdf", "fastjet-cxx", "fastjet-contrib", "pythia8", "herwig",
                 "thepeg", "sherpa", "delphes", "geant4", "hdf5", "onnxruntime-cpp"):
        assert name in deps, name
    for name in ("root", "rivet", "pythia8", "herwig"):
        assert f"{name}: ready-made from conda-forge" in out.err and f"# == {name}" not in out.out, name
    for name in ("madgraph", "whizard", "pdfsets"):                           # not on conda-forge: built here
        assert f"# == {name}" in out.out, name
    whizard = next(line for line in out.out.splitlines() if "./configure" in line and "/whizard " in line)
    env = prefix / "base" / ".pixi" / "envs" / "default"
    assert f"--with-hepmc={env}" in whizard and f"--with-pythia8={env}" in whizard   # {dir_…}: the base's
    assert "fastjet-3.5.0" not in out.out and "root_v6.40.04" not in out.out           # nothing ready-made is fetched
    bs.main(["--list", "@core-conda", f"machine={prefix}"])
    listing = capsys.readouterr().out
    assert any(line.startswith("root ") and " conda " in line for line in listing.splitlines())
    assert "base:    conda-forge, not made yet" in listing


def test_a_ready_made_package_brings_what_it_needs_ready_made_too(bs, tmp_path):
    """Two FastJets, conda-forge's under a ready-made Rivet and the stack's, would be one too many."""
    with pytest.raises(SystemExit, match="rivet from conda-forge brings its own fastjet-cxx, and fastjet would be built"):
        bs.main(["--dry-run", f"machine={tmp_path}", "packages=rivet", "rivet.from=conda-forge",
                 "yoda.from=conda-forge", "hepmc3.from=conda-forge"])
    with pytest.raises(SystemExit, match="names no conda package"):
        bs.options([f"machine={tmp_path}", "whizard.from=conda-forge"])
    with pytest.raises(SystemExit, match='needs base = "conda"'):
        bs.options([f"machine={tmp_path}", "base=system", "root.from=conda-forge"])
    with pytest.raises(SystemExit, match="from is"):
        bs.options([f"machine={tmp_path}", "root.from=brew"])


def test_a_ready_made_package_is_where_conda_forge_put_it(bs, tmp_path):
    (order, _), packages, c = planned(bs, tmp_path, "packages=@core-conda")
    assert c["dir_root"] == c["base"] == c["venv"] and c["dir_rivet"] == c["base"]
    assert bs.state("root", packages["root"], c) == ""                       # not in the base yet
    a_base(c, root="6.40.04", python="3.12.15")
    c = bs.context(bs.options([f"machine={tmp_path}", "packages=@core-conda"])[1])
    assert bs.state("root", packages["root"], c) == "ready-made" and bs.present("root", packages["root"], c)
    assert bs.scope("root", packages["root"], c)["install"] == c["base"]
    (order, _), packages, c = planned(bs, tmp_path, "packages=rivet")
    assert c["dir_fastjet"] == f"{c['inst']}/fastjet" and c["dir_lhapdf"] == f"{c['inst']}/LHAPDF"


def test_a_change_in_the_bases_libraries_marks_what_was_built_on_them(bs, tmp_path):
    """A stamp holds the base's libraries (docs/conda/02 §4): gsl's build changing makes every package built
    here "changed"; pandoc's (a tool) changes nothing; the system base never had any."""
    _, s, packages = bs.options([f"machine={tmp_path}"])
    c = bs.context(s)
    a_base(c, python="3.12.15", gsl="2.8", pandoc="3.12.1", libstdcxx="15.3.0")
    c = bs.context(s)
    stamped(bs, tmp_path, "fastjet", packages=packages, c=c)
    assert c["base_hash"] and bs.state("fastjet", packages["fastjet"], c) == "built"
    a_base(c, python="3.12.15", gsl="2.8", pandoc="3.13.0", libstdcxx="15.3.0")
    assert bs.state("fastjet", packages["fastjet"], bs.context(s)) == "built"
    a_base(c, python="3.12.15", gsl="2.9", pandoc="3.13.0", libstdcxx="15.3.0")
    assert bs.state("fastjet", packages["fastjet"], bs.context(s)) == "changed"
    _, old, _ = bs.options([f"machine={tmp_path / 'old'}", "base=system"])
    assert bs.context(old)["base_hash"] == "" and bs.context(old)["base"] == ""


def test_the_activation_is_conda_s_less_the_compile_flags(bs, tmp_path):
    """base/activate.sh runs the base's activate.d (the compilers' CC, CXX …) and leaves CFLAGS & co. unset:
    the build and rules.mk set their own. setup.sh sources it; quit takes it out (test_setup.py)."""
    _, s, _ = bs.options([f"machine={tmp_path}"])
    c = bs.context(s)
    hook = Path(c["base"]) / "etc" / "conda" / "activate.d"
    hook.mkdir(parents=True)
    (hook / "activate-gxx.sh").write_text("export CXX=x86_64-conda-linux-gnu-c++ CXXFLAGS='-march=nocona'\n")
    Path(c["base_dir"], "activate.sh").write_text(bs.activate_text(c))
    env = bs.activation(c, {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CFLAGS": "-O3"})
    assert env["CONDA_PREFIX"] == c["base"] and env["PATH"].startswith(f"{c['base']}/bin:")
    assert env["CXX"] == "x86_64-conda-linux-gnu-c++" and "CXXFLAGS" not in env and "CFLAGS" not in env
    assert subprocess.run(["bash", "-n", str(Path(c["base_dir"], "activate.sh"))]).returncode == 0


def test_a_ready_made_root_sets_the_stacks_standard_and_pins_its_build(bs, tmp_path):
    """conda-forge builds ROOT for C++20 and 23 only: taken ready-made, it makes the stack C++20, so what is
    built here against it matches, and the base asks for that build; a standard set otherwise is refused."""
    import tomllib
    (order, _), packages, c = planned(bs, tmp_path, "packages=@core-conda")
    assert c["cxx_std"] == 20 and bs.ORIGINS["cxx_std"] == ["root from conda-forge (built for C++20 or C++23)"]
    deps = tomllib.loads(bs.manifest_text(order, packages, c))["dependencies"]
    assert deps["root"] == "*" and deps["root_base"] == {"version": "*", "build": "cxx20*"}
    (order, _), packages, c = planned(bs, tmp_path, "packages=@core-conda", "cxx_std=23")      # one of them
    assert tomllib.loads(bs.manifest_text(order, packages, c))["dependencies"]["root_base"]["build"] == "cxx23*"
    with pytest.raises(SystemExit, match=r"root from conda-forge is built for C\+\+20 or C\+\+23, and cxx_std = 17"):
        bs.options([f"machine={tmp_path}", "packages=@core-conda", "cxx_std=17"])
    assert planned(bs, tmp_path, "packages=@standard")[2]["cxx_std"] == 17            # built here: the stack's own


def test_what_the_base_holds_ready_made_stays_so(bs, tmp_path):
    """A root made with an @…-conda toolkit is read without it (hep doctor, hep stack status, a later build):
    a recipe whose package is in the base, and which the stack did not build, is the base's."""
    _, s, _ = bs.options([f"machine={tmp_path}"])
    a_base(bs.context(s), python="3.12.15", root="6.40.04", fastjet_cxx="3.5.2")
    _, s, packages = bs.options([f"machine={tmp_path}"])
    assert bs.ready_made(packages["root"]) and bs.ready_made(packages["fastjet"]) and not bs.ready_made(packages["rivet"])
    assert bs.ORIGINS["root.from"] == ["the base (ready-made there)"] and s["cxx_std"] == 20
    (tmp_path / "stack" / "fastjet").mkdir(parents=True)                        # built here: the stack's
    _, s, packages = bs.options([f"machine={tmp_path}", "root.from=source"])    # a layer's `from` wins
    assert not bs.ready_made(packages["fastjet"]) and not bs.ready_made(packages["root"]) and s["cxx_std"] == 17
    _, s, packages = bs.options([f"machine={tmp_path}", "base=system"])
    assert not bs.ready_made(packages["root"])


def test_the_base_gets_the_pkg_config_files_conda_forge_lacks(bs, tmp_path):
    """conda-forge's toml++ ships no tomlplusplus.pc, which env/stack.toml's probe asks pkg-config for: the
    base gets one in base/pkgconfig/, which activate.sh puts on PKG_CONFIG_PATH."""
    _, s, _ = bs.options([f"machine={tmp_path}"])
    c = bs.context(s)
    a_base(c, python="3.12.15")
    assert bs.pkgconfig_files(bs.context(s)) == {}
    a_base(c, python="3.12.15", tomlplusplus="3.4.0")
    files = bs.pkgconfig_files(bs.context(s))
    assert list(files) == ["tomlplusplus"] and "Version: 3.4.0\n" in files["tomlplusplus"]
    assert f"Cflags: -I{c['base']}/include\n" in files["tomlplusplus"]
    Path(c["base_dir"], "activate.sh").write_text(bs.activate_text(c))
    env = bs.activation(c, {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "PKG_CONFIG_PATH": "/x"})
    assert env["PKG_CONFIG_PATH"] == f"{c['base_dir']}/pkgconfig:/x"

