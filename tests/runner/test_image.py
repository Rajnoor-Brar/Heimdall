"""Apptainer images (runner/image.py, launch.sh --image; V150). Nothing runs Apptainer here: a fake runtime on
PATH (a script, as the real one is a program) records what it was asked."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from runner import image, paths
from runner.errors import HeimdallError

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """A fake `apptainer` first on PATH: its arguments to calls.txt, its definition file copied beside them."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "apptainer").write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$(dirname "$0")/calls.txt"\n'
                                    'for a; do case "$a" in *.def) cp "$a" "$(dirname "$0")/seen.def" ;; esac; done\n',
                                    encoding="utf-8")
    (bin_ / "apptainer").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
    monkeypatch.setenv("HEIMDALL_MACHINE", str(tmp_path / "Himinbjorg"))
    (tmp_path / "Himinbjorg" / "images").mkdir(parents=True)
    return bin_


def test_the_definition_is_filled_or_refused():
    text = image.render({"HEIMDALL": "/tmp/h", "PACKAGES": "@core-conda", "CORES": "4", "ROOT_CORES": "2",
                         "REVISION": "abc", "BUILT": "2026-10-14"})
    assert "    /tmp/h /opt/heimdall" in text and 'packages="@core-conda"' in text and "cores=4 root_cores=2" in text
    assert "heimdall.revision abc" in text and "shell_rc=false" in text and "Bootstrap: docker" in text
    with pytest.raises(HeimdallError, match="not given"):
        image.render({"HEIMDALL": "/tmp/h"})


def test_an_image_by_name_or_path(fake, tmp_path):
    (tmp_path / "Himinbjorg" / "images" / "core-conda.sif").write_text("x", encoding="utf-8")
    assert image.image_path("core-conda") == tmp_path / "Himinbjorg" / "images" / "core-conda.sif"
    with pytest.raises(HeimdallError, match="no image") as missing:
        image.image_path("core-cond")
    assert "'core-conda'" in missing.value.hint
    assert image.runtime() == str(fake / "apptainer")


def test_a_build_takes_a_clean_copy_with_fakeroot(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(image, "dirty", lambda: True)
    with pytest.raises(HeimdallError, match="uncommitted changes"):
        image.build("@core-conda", out=lambda _: None)
    monkeypatch.setattr(image, "dirty", lambda: False)
    assert image.build("@core-conda", cores="4", out=lambda _: None) == 0
    [call] = (fake / "calls.txt").read_text(encoding="utf-8").splitlines()
    words = call.split()
    assert words[:2] == ["build", "--fakeroot"] and words[2] == str(tmp_path / "Himinbjorg" / "images" / "core-conda.sif")
    seen = (fake / "seen.def").read_text(encoding="utf-8")
    assert 'packages="@core-conda"' in seen and "cores=4" in seen and "{{" not in seen.split("\nBootstrap", 1)[1]


def test_a_point_in_an_image_records_it(tmp_path, monkeypatch):
    assert image.inside() is None or os.environ.get("APPTAINER_CONTAINER")
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"heimdall.revision": "abc", "org.label-schema.x": "y"}), encoding="utf-8")
    monkeypatch.setattr(image, "LABELS", labels)
    monkeypatch.setenv("APPTAINER_CONTAINER", "/images/core.sif")
    assert image.inside() == {"path": "/images/core.sif", "labels": {"heimdall.revision": "abc"}}


def test_launch_runs_in_an_image_with_a_clean_environment(fake, tmp_path, monkeypatch):
    (tmp_path / "Himinbjorg" / "images" / "core.sif").write_text("x", encoding="utf-8")
    study = tmp_path / "Study"
    study.mkdir()
    (study / "heimdall.toml").write_text('[work]\nname = "Demo"\n', encoding="utf-8")
    monkeypatch.setenv("HEIMDALL_WORKDIRS", str(tmp_path / "workdirs.toml"))
    from runner import workdirs
    workdirs.record(study)
    env = {**os.environ}
    sif = tmp_path / "Himinbjorg" / "images" / "core.sif"
    done = subprocess.run([str(REPO / "launch.sh"), "--image", "core", "heimdall", "where"], cwd=tmp_path, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    done = subprocess.run([str(REPO / "launch.sh"), "--gjallarhorn", "--image", "core", "--dev", "Demo"], cwd=tmp_path,
                          env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    first, second = (fake / "calls.txt").read_text(encoding="utf-8").splitlines()
    assert first == f"exec --cleanenv --bind {tmp_path} --pwd {tmp_path} {sif} /opt/heimdall/launch.sh heimdall where"
    assert second == f"exec --cleanenv --bind {study} --bind {REPO}:/opt/heimdall --pwd {study} {sif} /opt/heimdall/launch.sh"
