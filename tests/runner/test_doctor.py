"""`hep doctor` and recipes/verify.py (docs/audit_3/06_Plan.md, phase 2.1): a package's checks from its
recipe, the scan for libraries that no longer resolve, the report and the support matrix."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from runner import doctor, plugins

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def verify():
    return plugins.load(REPO / "recipes" / "verify.py", "verify")


def rows(verify, entries, tmp_path, quick=False):
    return verify.run("pkg", entries, lambda text: text.replace("{dir}", str(tmp_path)), sys.executable,
                      {"PATH": "/usr/bin:/bin"}, quick=quick)


def test_each_kind_of_check(verify, tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "libX.so").touch()
    out = rows(verify, [
        {"name": "says hello", "command": "echo hello world", "has": ["hello"]},
        {"name": "says goodbye", "command": "echo hello", "has": ["goodbye"]},
        {"name": "fails", "command": "sh -c 'echo error: broken >&2; exit 3'"},
        {"name": "python", "python": "print('events', 100)", "expect": "^events 100"},
        {"name": "wrong output", "python": "print('events', 99)", "expect": "^events 100"},
        {"name": "files", "files": ["{dir}/lib/libX.*"]},
        {"name": "files lost", "files": ["{dir}/lib/libY.*"]},
        {"name": "slow", "command": "true", "slow": True},
    ], tmp_path, quick=True)
    results = {name: (result, note) for _, name, result, note in out}
    assert results["says hello"][0] == "ok"
    assert results["says goodbye"] == ("MISSING", "goodbye")
    assert results["fails"] == ("FAIL", "error: broken")
    assert results["python"][0] == "ok" and results["wrong output"][0] == "FAIL"
    assert results["files"][0] == "ok" and results["files lost"] == ("MISSING", "libY.*")
    assert results["slow"][0] == "n/a"


def test_a_bad_entry_is_named(verify):
    assert verify.problems("x", [{"name": "a"}])                     # no kind
    assert verify.problems("x", [{"name": "a", "command": "true", "files": []}])   # two kinds
    assert verify.problems("x", [{"command": "true"}])                # no name
    assert verify.problems("x", [{"name": "a", "command": "true", "colour": 1}])
    assert not verify.problems("x", [{"name": "a", "command": "true", "expect": "x"}])


def test_every_recipes_checks_are_well_formed(verify):
    import tomllib
    packages = tomllib.loads((REPO / "recipes" / "packages.toml").read_text(encoding="utf-8"))
    checked = [name for name, p in packages.items() if p.get("verify")]
    for name in checked:
        assert not verify.problems(name, packages[name]["verify"]), name
    primary = {"python", "lhapdf", "hepmc3", "fastjet", "fjcontrib", "root", "hdf5", "yoda", "rivet", "pythia8",
               "thepeg", "herwig", "delphes", "pdfsets", "sherpa", "madgraph", "whizard", "onnxruntime", "geant4",
               "madanalysis5"}
    assert primary <= set(checked)                                    # every @primary package says what it must do


def test_the_scan_finds_a_library_that_no_longer_resolves(verify, tmp_path, monkeypatch):
    lib = tmp_path / "pkg" / "lib"
    lib.mkdir(parents=True)
    (lib / "libA.so").write_bytes(b"\x7fELF" + b"\0" * 60)
    (lib / "readme.txt").write_text("not a binary")
    monkeypatch.setattr(verify, "links_of", lambda path: "\tlibgsl.so.27 => not found\n\tlibpython3.12.so.1.0 => not found\n")
    monkeypatch.setattr(verify, "MAC", False)
    checked, lost = verify.scan(tmp_path / "pkg")
    assert checked == 1 and lost == ["libgsl.so.27 (libA.so)"]        # libpython comes from the interpreter


def test_the_report_and_the_support_matrix(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "hep_root", lambda: tmp_path)
    sample = [("system", "os", "ok", "Linux x86_64"), ("root", "version", "ok", "6.40.04"),
              ("root", "libraries (root/)", "FAIL", "libgsl.so.27 (libMathMore.so)"),
              ("whizard", "linked", "MISSING", "not linked: LHAPDF")]
    text = "\n".join(doctor.render(sample, colour=False))
    assert "root\n  version" in text and "summary: ok 2, MISSING 1, FAIL 1, n/a 0" in text
    path = doctor.record(sample)
    assert path.parent == tmp_path / "recipes" / "support"
    table = "\n".join(doctor.matrix())
    assert path.stem in table and "root: libraries (root/): FAIL: libgsl.so.27" in table
