"""framework/tools/sherpa/prepare.py: Sherpa's prepare step compiles what Amegic wrote and runs Sherpa again,
and a run that sets up no process says why (2026-10-24)."""

from __future__ import annotations

import importlib.util
import os
import stat
from pathlib import Path

import pytest

HELPER = Path(__file__).resolve().parents[2] / "framework" / "tools" / "sherpa" / "prepare.py"

#: Sherpa as each case behaves: the run's number in ./count, its kind in $FAKE_SHERPA.
FAKE = """#!/bin/bash
n=$(( $(cat count 2>/dev/null || echo 0) + 1 )); echo $n > count
echo "$@" > argv.$n
case "$FAKE_SHERPA" in
  amegic)                        # Amegic's first run writes code and makelibs; the next integrates
    if [ ! -f compiled ]; then
      printf '#!/bin/bash\\necho "$@" > makelibs.argv\\ntouch compiled\\n' > makelibs
      printf 'Normal exit thrown:\\nSource code created in %s. Run '"'"'./makelibs'"'"' there to compile.\\n' "$PWD"
    else
      printf 'Starting the calculation\\r 50%%\\rdone\\n'; touch Results.zip
    fi ;;
  comix) echo "Starting the calculation"; touch Results.zip ;;
  nohard)
    echo "Matrix_Element_Handler::BuildSingleProcessList(): Error in initialising ISR (P+ -> e+) x (e+ -> j). Ignoring process."
    echo "No hard process found" ;;
  crash) echo "Signal (11) caught"; exit 139 ;;
esac
"""


@pytest.fixture
def prepare(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("sherpa_prepare", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake = tmp_path / "bin" / "Sherpa"
    fake.parent.mkdir()
    fake.write_text(FAKE, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    entry = tmp_path / "cache"
    entry.mkdir()
    monkeypatch.chdir(entry)
    monkeypatch.delenv(module.JOBS_VAR, raising=False)

    def call(kind: str) -> tuple[int, Path]:
        monkeypatch.setenv("FAKE_SHERPA", kind)
        return module.main([str(fake), "-f", "card.yaml", "-e", "0"]), entry
    return call


def runs(entry: Path) -> int:
    return int((entry / "count").read_text(encoding="utf-8"))


def test_an_amegic_card_is_compiled_then_integrated(prepare, capfd):
    code, entry = prepare("amegic")
    assert code == 0 and (entry / "Results.zip").exists() and runs(entry) == 2
    assert (entry / "makelibs.argv").read_text(encoding="utf-8").split() == ["-j", "1"]
    assert (entry / "argv.1").read_text(encoding="utf-8") == (entry / "argv.2").read_text(encoding="utf-8")
    out = capfd.readouterr().out
    assert "Run './makelibs' there to compile." in out and "Starting the calculation\r 50%\rdone" in out


def test_the_compile_takes_its_jobs_from_the_environment(prepare, monkeypatch):
    monkeypatch.setenv("HEP_MAKELIBS_JOBS", "6")
    code, entry = prepare("amegic")
    assert code == 0 and (entry / "makelibs.argv").read_text(encoding="utf-8").split() == ["-j", "6"]


def test_a_comix_card_is_one_run(prepare):
    code, entry = prepare("comix")
    assert code == 0 and runs(entry) == 1 and not (entry / "makelibs").exists()


def test_no_hard_process_says_why(prepare, capfd):
    """Sherpa exits 0 having set up nothing: the step fails, quoting Sherpa's reasons."""
    code, entry = prepare("nohard")
    last = capfd.readouterr().out.strip().splitlines()[-1]
    assert code == 3 and runs(entry) == 1 and not (entry / "Results.zip").exists()
    assert last.startswith("Error: Sherpa ended without its Results: Error in initialising ISR (P+ -> e+)")
    assert last.count("No hard process found") == 1


def test_a_crash_passes_its_exit_on(prepare):
    code, entry = prepare("crash")
    assert code == 139 and runs(entry) == 1
