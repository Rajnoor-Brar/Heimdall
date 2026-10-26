"""Run logging (V195): what a run saves is clean text, what Sherpa says mid-line is read, a stall says
where it stopped, and the views keep a message's own brackets."""

from __future__ import annotations

import os
import re
import time
import tomllib
from pathlib import Path

import pytest

from runner import cli, execute, hepfiles, tools
from runner.events import Bus
from runner.status import Reader, ToolState, clean, clean_text

from helpers import plans, plans_of

TESTS = Path(__file__).resolve().parents[1]
LOGS = TESTS / "fixtures" / "logs"
SHERPA_RULES = tomllib.loads((TESTS.parent / "framework/tools/sherpa/filters.toml").read_text(encoding="utf-8"))["rule"]
#: What no saved text may hold: an escape, or a control character but tab and newline.
CLUTTER = re.compile(rb"\x1b|[\x00-\x08\x0b-\x1f\x7f]")


def read_through(scratch: Path, chunks: list[bytes], rules=(), keep: bool = True, pause: float = 0.0):
    """A tool's output read as the runner reads it, the chunks written in turn; its reader, its log and the
    events it sent."""
    events: list[dict] = []
    bus = Bus()
    bus.subscribe(events.append)
    read, write = os.pipe()
    log = scratch / "tool.log"
    reader = Reader(ToolState("p", "sherpa"), fd=None, out=read, rules=list(rules), bus=bus, log=log, keep=keep)
    for chunk in chunks:
        os.write(write, chunk)
        time.sleep(pause)
    os.close(write)
    reader.join()
    return reader, log, events


def logged(events: list[dict], level: str) -> list[str]:
    return [e["msg"] for e in events if e.get("k") == "log" and e.get("level") == level]


# ── clean text ─────────────────────────────────────────────────────────────────────────────────────────

def test_saved_text_holds_no_terminal_clutter(scratch):
    data = (b"\x1b[1m\x1b[31mError\x1b[0m in it\x07\n"            # colours and a bell
            b"a\ttab stays\n"
            b"\x1b]0;a window title\x07after the title\n"           # an OSC
            b"\x1b(Bcharset chosen\n"                                # a character set's choice
            b"\x1b[?25hcursor shown\x1b[1A\n")                       # cursor commands (Sherpa's)
    _, log, _ = read_through(scratch, [data])
    saved = log.read_bytes()
    assert not CLUTTER.search(saved)
    assert saved.decode("utf-8").splitlines() == ["Error in it", "a\ttab stays", "after the title", "charset chosen",
                                                  "cursor shown"]


def test_a_rewritten_line_is_saved_at_its_last_state(scratch):
    _, log, _ = read_through(scratch, [b"one\n", b"counter 1\rcounter 2\r", b"counter 3\rtwo\n", b"left at 50%\r"],
                             pause=0.05)
    assert log.read_text(encoding="utf-8") == "one\ntwo\nleft at 50%\n"         # the last state, as a terminal shows it


def test_a_crlf_two_reads_cut_is_one_line_end(scratch):
    _, log, _ = read_through(scratch, [b"line one\r", b"\nline two\r\n"], pause=0.2)
    assert log.read_text(encoding="utf-8") == "line one\nline two\n"


def test_a_failed_tools_tail_is_clean_too(scratch):
    reader, log, _ = read_through(scratch, [b"\x1b[31mlast words\x1b[0m\n"], keep=False)
    reader.keep_tail()
    assert log.read_text(encoding="utf-8") == "last words\n"


def test_captured_output_is_cleaned_line_by_line():
    assert clean("\x1b[33m\x1b[1mWARNING\x1b[0m: x\x08") == "WARNING: x"
    assert clean_text("50%\r100%\r\nnext\x1b[0m\n") == "100%\nnext\n"


# ── what Sherpa says ───────────────────────────────────────────────────────────────────────────────────

def test_sherpas_dropped_process_and_nan_are_errors(scratch):
    _, log, events = read_through(scratch, [(LOGS / "sherpa_dropped_process.log").read_bytes()], SHERPA_RULES)
    errors = logged(events, "error")
    assert any("Error in initialising ISR (e+ -> j) x (P -> j). Ignoring process." in e for e in errors)
    assert any("Cross section is 'nan'" in e for e in errors)
    assert not any("Normal exit" in e for e in errors)                   # Sherpa's own way out, not an error
    assert not CLUTTER.search(log.read_bytes())


def test_an_undefined_tag_is_the_error_it_is(scratch):
    _, _, events = read_through(scratch, [(LOGS / "sherpa_undefined_tag.log").read_bytes()], SHERPA_RULES)
    assert any("Could not find a definition for `$(LOOPGEN)'" in e for e in logged(events, "error"))


def test_sherpas_routine_errors_are_warnings(scratch):
    _, _, events = read_through(scratch, [(LOGS / "sherpa_routine.log").read_bytes()], SHERPA_RULES)
    warnings = " | ".join(logged(events, "warn"))
    for said in ("Singlet_Sorter", "hope for the best", "exceeded frequency limit", "last allowed error message",
                 "pilot run and the re-run", "Some settings that have been defined"):
        assert said in warnings
    assert logged(events, "error") == []


# ── a stall ────────────────────────────────────────────────────────────────────────────────────────────

def test_a_stall_says_since_when_and_what_it_was_doing():
    state = ToolState("p", "sherpa:prepare", phase="integrating", last_line="Starting the calculation at 20:29:41")
    clock = time.monotonic()
    state.last_activity = clock - 5200
    said = execute.stalled("sherpa:prepare", 5200, state, clock)
    since = time.strftime("%H:%M", time.localtime(time.time() - 5200))
    assert said == (f"sherpa:prepare was silent for 5200 s, since {since} "
                    '(integrating; last line: "Starting the calculation at 20:29:41")')
    assert execute.stalled("x", 300, ToolState("p", "x"), time.monotonic()).startswith("x was silent for 300 s, since ")


# ── the views and the title ────────────────────────────────────────────────────────────────────────────

def test_the_live_view_keeps_a_messages_brackets():
    rich_text = pytest.importorskip("rich.text")
    from runner.watch import LiveView
    said = "where: [quantities.pdf] = NNPDF23lo"
    assert rich_text.Text.from_markup(LiveView._text(LiveView.__new__(LiveView), said)).plain == said


def test_a_runs_title_is_its_name_serial_and_configuration_then_its_size():
    run, configuration, _, _ = plans_of("Demo/sherpa", "single")
    title = cli.run_title(run, configuration, plans("Demo/sherpa", "single"))
    assert title.split("\n") == ["sherpa · 04  ·  single", "   - 1 point(s), 5000 events, 1 threads"]


# ── where a rendered card's lines come from ────────────────────────────────────────────────────────────

def test_a_rendered_card_says_who_set_each_key():
    p = plans("Demo/sherpa", "pdf")[0]
    shown = {line.split(":", 1)[0].strip(): line.rsplit("←", 1)[-1].strip()
             for line in tools.card_view(p, "sherpa")[1:] if "←" in line and re.match(r"  [A-Z_]+:", line)}
    assert shown["PDF_SET"].startswith("[quantities.pdf] = ")
    assert shown["MPI_PDF_SET"].startswith("PDF_SET's ([quantities.pdf] = ")
    assert shown["EVENTS"] == "built-in events"
    assert shown["RANDOM_SEED"] == "the plan"
    assert "the base card" in shown.values()


# ── an analysis that filled nothing ────────────────────────────────────────────────────────────────────

HISTO = """BEGIN YODA_HISTO1D_V3 /RAW/A/{name}
Path: /RAW/A/{name}
Type: Histo1D
---
Edges(A1): [0.000000e+00, 1.000000e+00]
# sumW       	sumW2        	sumW(A1)     	sumW2(A1)    	numEntries
0.000000e+00 	0.000000e+00 	0.000000e+00 	0.000000e+00 	0.000000e+00
{w} 	{w} 	{w} 	{w} 	{w}
0.000000e+00 	0.000000e+00 	0.000000e+00 	0.000000e+00 	0.000000e+00
END YODA_HISTO1D_V3
"""
COUNTER = """BEGIN YODA_COUNTER_V3 /RAW/_EVTCOUNT
Path: /RAW/_EVTCOUNT
Type: Counter
---
# sumW       	sumW2        	numEntries
1.000000e+04 	1.000000e+04 	1.000000e+04
END YODA_COUNTER_V3
"""


def test_the_histograms_with_entries_are_counted(scratch):
    path = scratch / "a.yoda"
    path.write_text(HISTO.format(name="d01", w="0.0") + HISTO.format(name="d02", w="3.0") + COUNTER, encoding="utf-8")
    assert hepfiles.filled(path) == (1, 2)                      # the counter is not a histogram
    assert hepfiles.filled(scratch / "missing.yoda") is None


def test_a_rivet_that_filled_nothing_says_so():
    p = plans("Demo/jets")[0]
    rivet = next(s for s in p.rendered.values() if s.folder.name == "rivet")
    final = next(f for f, _ in rivet.products if f.suffix == ".yoda")
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_text(HISTO.format(name="d01", w="0.0") + COUNTER, encoding="utf-8")
    try:
        assert execute.empty_analyses([rivet]) == [f"   {rivet.tag}: no histogram filled (0 of 1) in {final.name}: "
                                                   "every event was vetoed"]
        final.write_text(HISTO.format(name="d01", w="2.0") + COUNTER, encoding="utf-8")
        assert execute.empty_analyses([rivet]) == []
    finally:
        final.unlink()


def test_the_plan_counts_totalitys_own_pages(capsys):
    assert cli.main(["run", "Demo/sherpa", "pdf", "--plan"]) == 0
    assert re.search(r"plot \(.*\): 1 page\(s\) per object in totality", capsys.readouterr().out)
