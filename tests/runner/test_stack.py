"""env/stack.toml (V78): one registry of the software stack, read by flags.sh, the Makefile (KNOWN),
the tool folders' versions and `heimdall status --stack`."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from runner import plugins, tools

REPO = Path(__file__).resolve().parents[2]
ENV = REPO / "env"


@pytest.fixture(scope="module")
def stack():
    return plugins.load(ENV / "stack.py", "stack")


def test_flags_sh_probes_what_the_stack_lists(stack):
    text = stack.bash()
    names = [n for n, e in stack.entries().items() if e.get("flags") or e.get("dir")]
    assert f"NAMES=({' '.join(names)})" in text
    assert "    probe pythia8 pythia8-config --cxxflags --ldflags" in text
    assert '    dir_lib delphes "${DELPHES_DIR:-${HEP_INSTALL-}/delphes}" Delphes' in text   # or the base's
    assert text.startswith("TOOLS=(") and "pkg-config" in text.splitlines()[0]


def test_the_flags_cache_says_what_is_known_and_keys_on_the_stack():
    key = subprocess.run([str(ENV / "flags.sh"), "--key"], capture_output=True, text=True, encoding="utf-8").stdout
    assert ";STACK=" in key
    from runner import paths
    flags = paths.forge_dir() / "make" / "flags.mk"                 # Heimdall's build (the machine root's forge/)
    if flags.exists():                                              # written by make, from the stack
        known = next((l for l in flags.read_text(encoding="utf-8").splitlines() if l.startswith("KNOWN := ")), "")
        assert known.split(" := ")[1].split() == [n for n, e in tomllib.loads((ENV / "stack.toml").read_text(encoding="utf-8")).items()
                                                  if e.get("flags") or e.get("dir")]


def test_every_tool_version_names_a_stack_entry(stack):
    """A tool folder's [identity] version = "stack:<name>" names an entry with a version."""
    for folder in tools.folders().values():
        command = folder.get("identity", "version")
        if isinstance(command, str):
            assert command.startswith("stack:"), folder.name
            assert stack.version_command(command.removeprefix("stack:")), folder.name


def test_a_file_version_reads_the_files_version_line(stack, monkeypatch, tmp_path):
    (tmp_path / "VERSION").write_text("version = 3.7.3\ndate = x\n", encoding="utf-8")
    monkeypatch.setenv("HEP_INSTALL", str(tmp_path / "x"))
    monkeypatch.setattr(stack, "entries", lambda: {"mg": {"version": {"file": str(tmp_path / "VERSION")}}})
    assert stack.version("mg") == "version = 3.7.3"
    assert stack.expand("${HEP_INSTALL-}/madgraph") == str(tmp_path / "x" / "madgraph")


def test_the_bases_flags_survive_make(tmp_path):
    """rules.mk's ON_BASE gives -Wl,-rpath,<base>/lib whole: a bare comma would end $(if)'s argument."""
    rules = (REPO / "framework" / "rules.mk").read_text(encoding="utf-8")
    lines = [line for line in rules.splitlines() if line.startswith(("comma ", "ON_BASE "))]
    mk = tmp_path / "base.mk"
    mk.write_text("\n".join(lines) + "\nall: ; @echo '$(ON_BASE)'\n", encoding="utf-8")

    def flags(**env):
        return subprocess.run(["make", "-s", "-f", str(mk)], env={"PATH": os.environ["PATH"], **env},
                              capture_output=True, text=True, encoding="utf-8").stdout.split()
    assert flags(HEP_BASE="/b") == ["-isystem", "/b/include", "-L/b/lib", "-Wl,-rpath,/b/lib"]
    assert flags() == []


def test_the_same_flags_under_a_new_key_keep_the_caches_time(tmp_path):
    """A re-probe that finds the same flags (env/stack.toml edited, a tool moved to an equal one) rebuilds
    nothing: flags.mk keeps its time. Flags that differ give it a new one."""
    out = tmp_path / "flags.mk"
    subprocess.run([str(ENV / "flags.sh"), str(out)], check=True, capture_output=True)
    text = out.read_text(encoding="utf-8")
    for changed, kept in (("FLAGS_KEY := ", True), ("FOUND := ", False)):
        out.write_text(text.replace(changed, changed + "old "), encoding="utf-8")
        os.utime(out, (1_000_000_000, 1_000_000_000))
        subprocess.run([str(ENV / "flags.sh"), str(out)], check=True, capture_output=True)
        assert (out.stat().st_mtime == 1_000_000_000) is kept and "old " not in out.read_text(encoding="utf-8")



@pytest.mark.skipif(not os.environ.get("HEP") or not __import__("shutil").which("pkg-config"),
                    reason="the environment, and pkg-config")
def test_a_module_requires_any_library_pkg_config_knows(tmp_path):
    """`// requires: pkg:<name>`: a library outside env/stack.toml (the base's, a recipe of the machine's), linked
    through pkg-config; a name pkg-config does not know is said."""
    lib = tmp_path / "lib"
    (lib / "include").mkdir(parents=True)
    (lib / "include" / "heimdalltest.h").write_text("inline int heimdall_test() { return 42; }\n", encoding="utf-8")
    (lib / "heimdalltest.pc").write_text(f"Name: heimdalltest\nDescription: a test\nVersion: 1.0\n"
                                         f"Cflags: -I{lib}/include\nLibs:\n", encoding="utf-8")
    work = tmp_path / "w"
    (work / "modules" / "P").mkdir(parents=True)
    (work / "Makefile").write_text((REPO / "framework" / "templates" / "work" / "Makefile").read_text(encoding="utf-8"),
                                   encoding="utf-8")
    (work / "modules" / "P" / "T.cc").write_text(
        '// requires: pkg:heimdalltest\n#include "heimdalltest.h"\nint main() { return heimdall_test() == 42 ? 0 : 1; }\n',
        encoding="utf-8")
    env = {**os.environ, "PKG_CONFIG_PATH": f"{lib}:{os.environ.get('PKG_CONFIG_PATH', '')}"}
    done = subprocess.run(["make", "-C", str(work), "modules/P/T.exe"], env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert done.returncode == 0, done.stderr
    assert subprocess.run([str(work / "build" / "P" / "T.exe")]).returncode == 0
    (work / "modules" / "P" / "U.cc").write_text("// requires: pkg:nosuch\nint main() { return 0; }\n", encoding="utf-8")
    done = subprocess.run(["make", "-C", str(work), "modules/P/U.exe"], env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert done.returncode != 0 and "requires 'pkg:nosuch', which pkg-config does not know" in done.stderr
