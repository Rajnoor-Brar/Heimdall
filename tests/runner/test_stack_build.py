"""recipes/build_stack.py: the stack's build, from packages.toml, settings.toml and toolkits.toml. Only
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
    (primary, _), _, _ = planned(bs, tmp_path, "packages=@primary")
    assert primary == everything + ["madanalysis5"]                  # the primary workflow: ~/HEP's and MadAnalysis 5


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
    assert "dd4hep 01-38  (a recipe not yet proven by a build)" in out.err
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
    bs.main(["--dry-run", f"prefix={prefix}", "packages=rivet", "system=false"])
    whole = capsys.readouterr().out
    assert "# == hepmc3" in whole and "--retry-all-errors" in whole and "-C -" in whole
    assert "cedar-tools.web.cern.ch/downloads/Rivet-4.1.4.tar.gz" in whole and "yoda.hepforge.org" in whole
    bs.main(["--dry-run", "--resume", f"prefix={prefix}", "packages=rivet", "system=false"])
    assert "# == hepmc3" not in capsys.readouterr().out


def test_pythia_and_rivet_come_from_where_they_live_now(bs, tmp_path):
    _, s, packages = bs.options([f"prefix={tmp_path}"])
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


def test_a_mac_without_its_overlay_is_sent_to_build_sh(bs, tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "MAC", True)
    _, s, packages = bs.options([f"prefix={tmp_path}"])
    with pytest.raises(SystemExit) as stop:
        bs.preflight(s, bs.context(s), [])
    assert "recipes/platforms/mac/build.sh" in str(stop.value)
    _, s, _ = bs.options(["--config", str(REPO / "recipes/platforms/mac/mac.toml"), f"prefix={tmp_path}"])
    monkeypatch.setenv("HOMEBREW_PREFIX", "/opt/homebrew")
    monkeypatch.setattr(bs.shutil, "which", lambda name: None if name == "brew" else "/usr/bin/" + name)
    bs.preflight(s, bs.context(s), [])                              # with mac.toml: no stop


def test_yoda_takes_hdf5_only_from_the_stack(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", f"prefix={prefix}", "packages=yoda", "system=false"])
    alone = next(line for line in capsys.readouterr().out.splitlines() if "./configure" in line and "/yoda " in line)
    assert "--disable-h5" in alone and "--enable-h5" not in alone
    bs.main(["--dry-run", f"prefix={prefix}", "packages=yoda hdf5", "system=false"])
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
    _, s, packages = bs.options([f"prefix={prefix}"]) if packages is None else (None, None, packages)
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
    _, s, packages = bs.options([f"prefix={prefix}"])
    c = bs.context(s)
    (Path(c["inst"]) / "fastjet").mkdir(parents=True)                # installed some other way: used
    stamped(bs, prefix, "hepmc3", packages=packages, c=c)
    bs.building("python", packages["python"], c).touch()             # an attempt that did not finish
    bs.main(["--dry-run", "--resume", f"prefix={prefix}", "packages=fastjet hepmc3 python", "system=false"])
    script = capsys.readouterr().out
    assert "# == fastjet" not in script and "# == hepmc3" not in script and "# == python" in script


def test_rebuild_takes_what_depends_on_it(bs, tmp_path, capsys):
    prefix = tmp_path / "hep"
    _, s, packages = bs.options([f"prefix={prefix}"])
    c = bs.context(s)
    for name in ("python", "lhapdf", "hepmc3", "fastjet", "thepeg", "herwig", "rivet"):
        stamped(bs, prefix, name, packages=packages, c=c)
    assert bs.rebuild_set(["thepeg"], packages, c) == ["thepeg", "herwig"]
    bs.main(["--dry-run", "--resume", "--rebuild", "thepeg", f"prefix={prefix}", "system=false"])
    script = capsys.readouterr().out
    assert "# == thepeg" in script and "# == herwig" in script and "# == rivet" not in script
    with pytest.raises(SystemExit):
        bs.main(["--dry-run", "--rebuild", "nope", f"prefix={prefix}"])


def test_overrides_append_and_reach_the_environment(bs, tmp_path, monkeypatch):
    monkeypatch.setenv("HOMEBREW_PREFIX", "/opt/homebrew")
    _, s, packages = bs.options(["--config", str(REPO / "recipes/platforms/mac/mac.toml"), f"prefix={tmp_path}",
                                 "root.extra+=-Dfoo=ON", "thepeg.extra+='LDFLAGS=-L/x -lc++'",
                                 "delphes.env.EXTRA=1", "env.MY_FLAG=yes", "pdf_sets=CT10,cteq6l1"])
    assert packages["root"]["extra"][-1] == "-Dfoo=ON" and "-Dcocoa=ON" in packages["root"]["extra"]
    assert packages["thepeg"]["extra"][-1] == "LDFLAGS=-L/x -lc++"
    assert packages["delphes"]["env"] == {"PYTHIA8": "{inst}/pythia8", "EXTRA": "1"}
    assert s["env"]["MY_FLAG"] == "yes" and s["pdf_sets"] == ["CT10", "cteq6l1"]


def test_another_cxx_standard_on_a_built_stack_is_refused(bs, tmp_path):
    prefix = tmp_path / "hep"
    stamps = prefix / "stack" / ".stamps"
    stamps.mkdir(parents=True)
    (stamps / "cxx_std").write_text("17\n")
    with pytest.raises(SystemExit) as stop:
        bs.main([f"prefix={prefix}", "cxx_std=20", "system=false", "packages=fastjet"])
    assert "would mix ABIs" in str(stop.value)


def test_the_macs_fixes_are_recipe_lines(bs, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bs, "MAC", True)
    monkeypatch.setenv("HOMEBREW_PREFIX", "/opt/homebrew")
    prefix = tmp_path / "hep"
    bs.main(["--dry-run", "--config", str(REPO / "recipes/platforms/mac/mac.toml"), f"prefix={prefix}", "packages=@primary"])
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
