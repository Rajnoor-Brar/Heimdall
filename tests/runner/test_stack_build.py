"""recipes/build_stack.py: the stack's build, from packages.toml, settings.toml and toolkits.toml. Only
plans and dry runs here (nothing is built or downloaded); every prefix is a tmp_path."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from runner import plugins

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bs():
    return plugins.load(REPO / "recipes" / "build_stack.py", "build_stack")


def planned(bs, prefix, *args):
    _, s, packages = bs.options([f"prefix={prefix}", *args])
    c = bs.context(s)
    return bs.plan(s, packages, c), packages, c


def test_core_and_all_follow_the_file(bs, tmp_path):
    (core, added), packages, _ = planned(bs, tmp_path)
    assert added == []
    assert core == [n for n, p in packages.items() if p.get("group", "core") == "core"]
    assert core[0] == "python" and core[-1] == "pdfsets"
    (everything, _), _, _ = planned(bs, tmp_path, "packages=all")
    assert everything == [n for n, p in packages.items() if p.get("group", "core") in ("core", "extra")]
    assert "evtgen" in packages and "evtgen" not in everything        # the toolkits' join only by name or @kit
    for name in everything:                                        # each after what it needs
        assert all(everything.index(need) < everything.index(name) for need in packages[name].get("needs", []))


def test_needs_are_added_only_when_missing(bs, tmp_path):
    (order, added), _, _ = planned(bs, tmp_path, "packages=rivet")
    assert order == ["python", "hepmc3", "yoda", "fastjet", "fjcontrib", "rivet"]
    assert added == order[:-1]
    stamps = tmp_path / "stack" / ".stamps"
    stamps.mkdir(parents=True)
    for name in ("python", "hepmc3-3.3.1", "yoda-2.1.3"):
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
    _, s, packages = bs.options([f"prefix={tmp_path}", "madgraph.release=3.6.2"])
    assert "/3.6.x/" in bs.tarball("madgraph", packages["madgraph"], bs.context(s))[1]   # {series}


@pytest.mark.parametrize("arg", ["corez=3", "root.relase=1", "nope.release=1", "bogus", "cores=abc",
                                 "packages=foo"])
def test_mistakes_are_refused(bs, tmp_path, arg):
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, arg)


def test_a_config_file_changes_and_adds_packages(bs, tmp_path):
    extra = tmp_path / "my.toml"
    extra.write_text('cores = 3\n[root]\nrelease = "6.40.06"\n'
                     '[mine]\nrelease = "1"\nurl = "https://x/mine-{release}.tgz"\nkind = "cmake"\nneeds = ["root"]\n')
    (order, added), packages, c = planned(bs, tmp_path, "--config", str(extra), "packages=mine", "cores=2")
    assert order == ["python", "root", "mine"] and added == ["python", "root"]
    assert c["cores"] == 2 and packages["root"]["release"] == "6.40.06"   # the command line wins over the file


def test_the_dry_run_is_a_bash_script_and_writes_nothing(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"prefix={prefix}", "packages=all", "system=false", "root_cores=2"])
    script = capsys.readouterr().out
    assert not prefix.exists()
    assert script.isascii()                                         # any locale can print and save it
    assert subprocess.run(["bash", "-n"], input=script, text=True).returncode == 0
    for line in ("set -euo pipefail", "-p0 -i " + str(REPO / "recipes/patches"), "--with-hepmcversion=3",
                 "make fragile-shared-install", f"cmake --build {prefix}/forge/root -j2",
                 f"-m venv --prompt HEP {prefix}/env/venv", f"{prefix}/env/venv/bin/python {REPO}/recipes/pth.py",
                 f"--with-root={prefix}/stack/root", "lhapdf install CT14lo CT14nlo", f"{prefix}/stash/root-6.40.04.tar.gz"):
        assert line in script, line
    assert "setup.sh <<" not in script and "machine.sh" not in script   # setup.sh is tracked; no extra lines on Linux
    assert script.index("# == root") < script.index("# == pythia8")


def test_the_mac_overlay(bs, tmp_path, monkeypatch, capsys):
    """recipes/platforms/mac/mac.toml as build.sh gives it, with macOS switched on: no apt, Homebrew's paths,
    ROOT through Cocoa, absolute install names, DYLD_LIBRARY_PATH, the macOS ONNX Runtime."""
    monkeypatch.setattr(bs, "MAC", True)
    monkeypatch.setenv("HOMEBREW_PREFIX", "/opt/homebrew")
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", "--config", str(REPO / "recipes/platforms/mac/mac.toml"), f"prefix={prefix}", "packages=all"])
    script = capsys.readouterr().out
    root = next(line for line in script.splitlines() if line.startswith(f"cmake -S {prefix}/stash/root "))
    assert root.index("-Dx11=OFF") < root.index("-Dcocoa=ON")        # the overlay's come last, and win
    assert "-DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3" in root
    assert f"-DCMAKE_INSTALL_NAME_DIR={prefix}/stack/hepmc3/lib" in script
    assert "-DCMAKE_INSTALL_NAME_DIR" not in next(line for line in script.splitlines()
                                                  if line.startswith(f"cmake -S {prefix}/stash/sherpa "))
    for line in ("export DYLD_LIBRARY_PATH=", "export CPPFLAGS=-I/opt/homebrew/include", "onnxruntime-osx-",
                 "sed -i.orig", "export DYLD_LIBRARY_PATH=$LD_LIBRARY_PATH",
                 "PATH=/opt/homebrew/opt/$_g/libexec/gnubin:$PATH", f"cat > {prefix}/env/machine.sh"):
        assert line in script, line
    assert "apt-get" not in script and "export LD_LIBRARY_PATH=" not in script
    assert subprocess.run(["bash", "-n"], input=script, text=True, encoding="utf-8").returncode == 0


def test_the_system_packages_carry_what_decks_need(bs, tmp_path):
    """hep deck (docs/reporter): pandoc for the slides, poppler for a figure's PNG, the Beamer class."""
    _, s, _ = bs.options([f"prefix={tmp_path}"])
    assert {"pandoc", "poppler-utils", "texlive-latex-recommended"} <= set(s["apt_packages"])


# ── toolkits (toolkits.toml, README.md §6) ─────────────────────────────────────────────────────

def test_every_toolkit_plans_and_names_only_packages(bs, tmp_path):
    _, _, packages = bs.options([f"prefix={tmp_path}"])
    kits = bs.toolkits()
    assert {"lab", "bsm-recast", "heavy-flavour", "detector", "key4hep"} <= set(kits)
    for name in kits:
        (order, _), _, _ = planned(bs, tmp_path, f"packages=@{name}")
        assert order, name
        for package in order:                                        # each after what it needs
            assert all(order.index(n) < order.index(package) for n in packages[package].get("needs", []) if n in order)
    (lab, _), _, _ = planned(bs, tmp_path, "packages=@lab")
    (everything, _), _, _ = planned(bs, tmp_path, "packages=all")
    assert lab == everything


def test_a_toolkit_brings_what_it_needs(bs, tmp_path):
    (order, added), _, _ = planned(bs, tmp_path, "packages=@heavy-flavour")
    assert order[-3:] == ["photospp", "tauolapp", "evtgen"]              # PHOTOS++ and TAUOLA++ before EvtGen
    assert "photospp" in added and "tauolapp" in added
    (mixed, _), _, _ = planned(bs, tmp_path, "packages=@data rivet")     # toolkits and names together
    assert {"highfive", "hepdata", "rivet"} <= set(mixed)


@pytest.mark.parametrize("arg", ["packages=@nope", "packages=@"])
def test_an_unknown_toolkit_is_refused(bs, tmp_path, arg):
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, arg)


def test_external_packages_are_never_built(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"prefix={prefix}", "packages=@key4hep @cms @fluka", "system=false"])
    out = capsys.readouterr()
    assert "# == key4hep" not in out.out and "curl" not in out.out   # nothing fetched, nothing run
    for name in ("key4hep", "cmssw", "fluka"):
        assert f"{name}: external" in out.err, name
    _, _, packages = bs.options([f"prefix={tmp_path}"])
    assert all(p.get("how") for p in packages.values() if p["kind"] == "external")


def test_new_recipes_say_so_and_bring_their_system_packages(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"prefix={prefix}", "packages=@detector"])
    out = capsys.readouterr()
    assert "dd4hep 01-38  (a new recipe" in out.err
    install = next(line for line in out.out.splitlines() if "apt-get install" in line)
    assert "libeigen3-dev" in install and "nlohmann-json3-dev" in install and "libxerces-c-dev" in install
    _, _, packages = bs.options([f"prefix={tmp_path}"])
    proven = [n for n, p in packages.items() if p.get("group", "core") in ("core", "extra")]
    assert not [n for n in proven if packages[n].get("status")]          # the lab PC's recipes are proven


# ── isolated toolkits and your own (toolkits.d) ────────────────────────────────────────────────

def test_an_isolated_toolkit_builds_a_stack_of_its_own(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"prefix={prefix}", "packages=@key4hep-src", "system=false"])
    script = capsys.readouterr().out
    base = prefix / "stacks" / "key4hep-src"
    root = next(line for line in script.splitlines() if line.startswith(f"cmake -S {prefix}/stash/root "))  # stash/ is shared
    assert f"-DCMAKE_INSTALL_PREFIX={base}/stack/root" in root and "-DCMAKE_CXX_STANDARD=20" in root
    assert f"-m venv --prompt HEP-key4hep-src {base}/venv" in script
    assert "-DGEANT4_BUILD_CXXSTD=20" in script                     # the toolkit's override
    assert f"cat > {base}/setup.sh" in script and "HEP_STACK_REQUEST=key4hep-src" in script
    assert f"{prefix}/stack/" not in script                           # the default stack is not touched


def test_the_default_stack_keeps_cxx17(bs, tmp_path):
    (_, _), _, c = planned(bs, tmp_path, "packages=@detector")
    assert c["cxx_std"] == 17 and c["stack"] == "" and c["inst"] == str(tmp_path.resolve() / "stack")


def write_kits(bs, monkeypatch, tmp_path, text):
    folder = tmp_path / "toolkits.d"
    folder.mkdir(exist_ok=True)
    (folder / "mine.toml").write_text(text, encoding="utf-8")
    monkeypatch.setattr(bs, "TOOLKITS_D", folder)


def test_your_own_toolkit_is_read_with_the_presets(bs, tmp_path, monkeypatch):
    write_kits(bs, monkeypatch, tmp_path, '[mine]\ndescription = "x"\npackages = ["@data", "rivet"]\n'
                                          '[mine.override.rivet]\nrelease = "4.1.4"\n')
    (order, _), packages, _ = planned(bs, tmp_path, "packages=@mine")
    assert {"highfive", "hepdata", "rivet"} <= set(order) and packages["rivet"]["release"] == "4.1.4"


@pytest.mark.parametrize("text", [
    '[lab]\npackages = ["core"]\n',                                   # a preset's name: refused, never replaced
    '[mine]\npackages = ["core"]\n[mine.settings]\ncxx_std = 20\n',    # another ABI without isolation
    '[mine]\npackages = ["core"]\ncolour = "red"\n',                   # an unknown key
    '[mine]\npackages = ["core"]\n[mine.override.nope]\nrelease = "1"\n',
])
def test_a_bad_toolkit_is_refused(bs, tmp_path, monkeypatch, text):
    write_kits(bs, monkeypatch, tmp_path, text)
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, "packages=@mine" if "[mine]" in text else "packages=@lab")


def test_one_isolated_stack_per_run(bs, tmp_path):
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, "packages=@key4hep-src @gpu-sim")
    with pytest.raises(SystemExit):
        planned(bs, tmp_path, "_stack=sneaky")                       # the internal key is not a setting
