"""The plot stage's failures logged (V204): a failed Paint batch's, converter's or merge's output,
cleaned and digested, in records/<run>/logs/plot/, the failure naming the file; nothing written when no drawing
is under way (heimdall plot FILE). The programs are small shell scripts in Paint's and App_yd2rt's place."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from runner import cli, house, plot
from runner.errors import HeimdallError


def script(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture
def logs(scratch):
    """A drawing under way, its log folder in the scratch."""
    folder = scratch / "records" / "logs" / "plot"
    token = plot._LOGS.set(folder)
    yield folder
    plot._LOGS.reset(token)


def test_a_failed_paint_batch_leaves_its_output_a_set_and_its_failed_pages_name_it(scratch, logs):
    paint = script(scratch / "Paint.exe", r'''echo -e "\x1b[31mloading\x1b[0m pages"
echo '{"page": "'"$1"'", "ok": true, "error": ""}'
echo '{"page": "'"$2"'", "ok": false, "error": "no such histogram"}'
echo "Error in <TFile::Open>: cannot open" >&2
exit 1''')
    configs = [scratch / "a.toml", scratch / "b.toml"]
    outcomes = plot._paint(paint, configs, sets={str(configs[0]): "spectra", str(configs[1]): "spectra"})
    log = logs / "spectra.root.log"
    assert outcomes[str(configs[0])] == (True, "")
    assert outcomes[str(configs[1])] == (False, f"no such histogram (Paint's output: {log})")
    text = log.read_text(encoding="utf-8")
    assert text.startswith("# tag Paint · batch 1 · pages 2 · exit 1 · ") and "\x1b" not in text
    assert "loading pages" in text and "Error in <TFile::Open>: cannot open" in text


def test_one_page_alone_and_a_crash(scratch, logs):
    paint = script(scratch / "Paint.exe", 'echo "drawing"; kill -SEGV $$')
    (config,) = configs = [scratch / "only.toml"]
    ok, why = plot._paint(paint, configs, sets={str(config): ""})[str(config)]
    assert not ok and why == f"Paint crashed (signal 11) (Paint's output: {logs / 'pages.root.log'})"
    assert (logs / "pages.root.log").read_text(encoding="utf-8").splitlines()[1] == "drawing"


def test_a_page_that_went_well_leaves_nothing(scratch, logs):
    paint = script(scratch / "Paint.exe", 'echo "fine"')
    assert plot._paint(paint, [scratch / "a.toml"]) == {str(scratch / "a.toml"): (True, "")}
    assert not logs.exists()


def test_no_drawing_under_way_no_log(scratch):
    paint = script(scratch / "Paint.exe", "exit 1")
    ok, why = plot._paint(paint, [scratch / "a.toml"])[str(scratch / "a.toml")]
    assert not ok and "Paint's output" not in why and plot.failure_log("x", "text", {}) is None


def test_a_failed_conversion_names_its_log(scratch, logs, monkeypatch):
    monkeypatch.setenv("HEIMDALL_APPS", str(scratch / "apps"))
    script(scratch / "apps" / "App_yd2rt.exe", 'echo "reading $1"; echo "bad YODA" >&2; exit 4')
    yoda = scratch / "MSTW.yoda"
    yoda.write_text("x\n", encoding="utf-8")
    with pytest.raises(HeimdallError, match=r"converting MSTW.yoda failed: bad YODA \(its output: .*convert-MSTW.log\)"):
        plot.convert(yoda, scratch / "MSTW.root")
    lines = (logs / "convert-MSTW.log").read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# tag App_yd2rt · yoda ") and " · exit 4 · 2 line(s)" in lines[0]
    assert lines[1:] == [f"reading {yoda}", "bad YODA"]


def test_a_drawings_logs_are_its_records_and_clean_keeps_them(scratch, monkeypatch):
    for var, name in (("HEIMDALL_RECORDS", "records"), ("HEIMDALL_CACHE", "cache"), ("HEIMDALL_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    p = cli.build_plans(argparse.Namespace(config="Demo/jets", set=[], points=None, rerun=False, only=None), "single")
    assert plot.logs_of(p.every) == p.every[0].folders.logs / "plot" and plot.logs_of([]) is None
    assert "plot" in house.KEEP_NAMES
