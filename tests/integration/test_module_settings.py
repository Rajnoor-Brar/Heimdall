"""A module program's settings (docs/audit_3/06_Plan.md, phase 4.2; src/Module.hh): every key of its
config must be one it reads, refused before the first event with the nearest name; --describe lists
them, and `hep explain <Name>.exe` shows them. On the scratch work's own Decay.exe."""

from __future__ import annotations

import subprocess

import pytest

from support import HEP, WORK

pytestmark = pytest.mark.slow


def test_a_misspelt_setting_is_refused_before_the_first_event(work_built, scratch):
    exe = WORK / "build" / "Decay" / "Decay.exe"
    config = scratch / "config.toml"
    config.write_text("bins = 10\nmas_tolerance = 0.1\n[quantities]\nsqrts = 100\n", encoding="utf-8")
    done = subprocess.run([str(exe), str(config), "--input=/nowhere.hepmc"], capture_output=True, text=True, timeout=60)
    assert done.returncode == 1                                          # Kit::Config, not an input error
    assert "unknown setting 'mas_tolerance' (did you mean 'mass_tolerance'?)" in done.stdout + done.stderr


def test_the_settings_are_described(work_built):
    exe = WORK / "build" / "Decay" / "Decay.exe"
    described = subprocess.run([str(exe), "--describe"], capture_output=True, text=True, timeout=60)
    assert described.returncode == 0 and '"name": "mass_tolerance"' in described.stdout
    shown = subprocess.run([str(HEP), "explain", "Decay.exe.mass_tolerance"], cwd=WORK, capture_output=True,
                           text=True, timeout=60)
    assert shown.returncode == 0 and "mass_tolerance" in shown.stdout and "0.15" in shown.stdout
