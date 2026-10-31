"""Paint against the legacy plotting (P3 S2 rows 2–3): ranges, voids and gutters, by --dump-ranges.

The legacy run (tests/reference/legacy_run) kept what its ydmrg step made from the two mini YODAs:
the voided copies (min_entries = 10, voided across both curves) and auto_range.plot (padded by one
bin, over the curves and the data). Paint must reproduce both for every object, from the raw YODAs.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import tomli_w

from support import apps  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PAINT = apps() / "Paint.exe"
YD2RT = apps() / "App_yd2rt.exe"
LEGACY = REPO / "tests" / "reference" / "legacy_run"
OBJECTS = [f"d{n:02d}-x01-y01" for n in range(1, 18)]

pytestmark = pytest.mark.skipif(not (PAINT.exists() and YD2RT.exists()), reason="Paint.exe, App_yd2rt.exe not built (heimdall build --framework)")


@pytest.fixture(scope="module")
def inputs(tmp_path_factory) -> dict[str, Path]:
    where = tmp_path_factory.mktemp("paint")
    out = {}
    for name, source in (("MSTW", LEGACY / "mini_27x920_ep_MSTW.yoda"), ("NNLO", LEGACY / "mini_27x920_ep_NNLO.yoda"),
                         ("data", LEGACY / "ydmrg" / "photo_eic_data.yoda")):
        out[name] = where / f"{name}.root"
        done = subprocess.run([str(YD2RT), str(source), str(out[name]), "--keep-raw"], capture_output=True, text=True, encoding="utf-8")
        assert done.returncode == 0, done.stderr
    out["dir"] = where
    return out


def page(inputs, obj: str, *, data: str | None = None, **keys) -> Path:
    document = {
        "page": {"name": obj, "output": str(inputs["dir"] / obj), **keys},
        "curve": [{"file": str(inputs[n]), "object": f"photo_eic/{obj}", "raw": f"RAW/photo_eic/{obj}", "label": n}
                  for n in ("MSTW", "NNLO")],
    }
    if data:
        document["data"] = {"file": str(inputs["data"]), "object": f"REF/photo_eic/{data}", "label": "data"}
    path = inputs["dir"] / f"{obj}.{abs(hash(json.dumps(keys, sort_keys=True, default=str)))}.toml"
    path.write_text(tomli_w.dumps(document), encoding="utf-8")
    return path


def dump(path: Path) -> dict:
    done = subprocess.run([str(PAINT), str(path), "--dump-ranges"], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def legacy_ranges() -> dict[str, tuple[float, float]]:
    text = (LEGACY / "ydmrg" / "auto_range.plot").read_text(encoding="utf-8")
    return {m[0]: (float(m[1]), float(m[2]))
            for m in re.findall(r"# BEGIN PLOT /photo_eic/(\S+)\nXMin=(\S+)\nXMax=(\S+)", text)}


def legacy_voids(name: str) -> dict[str, list[int]]:
    """1-based indices of the NaN bins of every Estimate1D in a legacy voided YODA."""
    text = (LEGACY / "ydmrg" / name).read_text(encoding="utf-8")
    out = {}
    for obj, body in re.findall(r"BEGIN YODA_ESTIMATE1D_V3 /photo_eic/(\S+)\n(.*?)END YODA", text, re.S):
        rows = [line.split()[0] for line in body.split("# value", 1)[1].splitlines()[1:] if line.strip()]
        out[obj] = [i for i, value in enumerate(rows[1:-1], start=1) if value == "nan"]   # without under/overflow
    return out


LEGACY_PAGE = {"void_empty": True, "min_entries": 10, "auto_range": True, "range_pad": 1}


def test_auto_range_equals_the_legacy_ranges(inputs):
    want = legacy_ranges()
    assert sorted(want) == OBJECTS
    for obj in OBJECTS:
        got = dump(page(inputs, obj, data=obj if obj <= "d12" else None, **LEGACY_PAGE))["x"]
        assert got == pytest.approx(list(want[obj]), rel=1e-5), obj      # the legacy file wrote %g


def test_voided_bins_equal_the_legacy_voids(inputs):
    mstw, nnlo = legacy_voids("void_000_mini_27x920_ep_MSTW.yoda"), legacy_voids("void_001_mini_27x920_ep_NNLO.yoda")
    assert sorted(mstw) == OBJECTS and mstw == nnlo                          # voided across the page
    for obj in OBJECTS:
        assert dump(page(inputs, obj, **LEGACY_PAGE))["voided"] == mstw[obj], obj


def test_y_gutter_puts_the_top_at_one_plus_the_gutter_times_the_largest(inputs):
    uproot = pytest.importorskip("uproot")
    for obj in ("d01-x01-y01", "d02-x01-y01", "d13-x01-y01"):
        ranges = dump(page(inputs, obj, auto_range=False, y_gutter=0.5))
        largest = max(max(uproot.open(inputs[n])[f"photo_eic/{obj}"].values()) for n in ("MSTW", "NNLO"))
        assert ranges["largest"] == pytest.approx(largest, rel=1e-9)
        assert ranges["y"][1] == pytest.approx(1.5 * largest, rel=1e-9)
        assert ranges["y"][0] == 0.0


def test_x_gutter_widens_symmetrically(inputs):
    plain = dump(page(inputs, "d02-x01-y01", **LEGACY_PAGE))["x"]
    wide = dump(page(inputs, "d02-x01-y01", x_gutter=0.2, **LEGACY_PAGE))["x"]
    assert wide[1] - wide[0] == pytest.approx(1.2 * (plain[1] - plain[0]))
    assert wide[0] + wide[1] == pytest.approx(plain[0] + plain[1])


def test_axis_ranges_override_only_the_requested_limits(inputs):
    plain = dump(page(inputs, "d02-x01-y01", auto_range=False))
    ranged = dump(page(inputs, "d02-x01-y01", auto_range=False, x_range=["default", 20], y_range=[-2, 1]))
    assert ranged["x"] == pytest.approx([plain["x"][0], 20])
    assert ranged["largest"] > ranged["y"][1]
    assert ranged["y"] == pytest.approx([-2, 1])
    assert not ranged["x_tool"] and not ranged["y_tool"]


def test_log_y_gutter_is_a_fraction_of_the_decades(inputs):
    ranges = dump(page(inputs, "d01-x01-y01", logy=True, y_gutter=0.5, **LEGACY_PAGE))
    low, high, largest = ranges["y"][0], ranges["y"][1], ranges["largest"]
    assert low > 0
    assert math.log10(high / largest) == pytest.approx(0.5 * math.log10(largest / low))


def test_a_zero_gutter_ends_the_axis_at_the_largest_value(inputs):
    """V55: 0 is a gutter like any other (no headroom); only "default" leaves the range to ROOT."""
    ranges = dump(page(inputs, "d02-x01-y01", y_gutter=0, **LEGACY_PAGE))
    assert not ranges["y_tool"] and ranges["y"][1] == pytest.approx(ranges["largest"], rel=1e-12)


def test_no_gutter_leaves_the_range_to_root(inputs):
    """"default": the range ROOT picks for one histogram holding every drawn value (THistPainter:
    5% of the span above and below, 0 if that crosses it; on a log axis ×0.5 below and ×2·0.9/0.95 above)."""
    for value in ("default",):
        linear = dump(page(inputs, "d02-x01-y01", y_gutter=value, x_gutter=value, **LEGACY_PAGE))
        assert linear["y_tool"] and not linear["x_tool"]                    # x is auto_range's, not the tool's
        assert linear["x"] == dump(page(inputs, "d02-x01-y01", **LEGACY_PAGE))["x"]
        top, bottom = linear["y"][1], linear["y"][0]
        assert 0.0 <= bottom < linear["largest"]                                 # d02 sits well above 0
        assert top == pytest.approx(linear["largest"] + 0.05 * (linear["largest"] - bottom), rel=1e-9)
        log = dump(page(inputs, "d01-x01-y01", logy=True, y_gutter=value, **LEGACY_PAGE))
        assert log["y"][1] == pytest.approx(log["largest"] * 2 * 0.9 / 0.95, rel=1e-9)
    assert dump(page(inputs, "d02-x01-y01", x_gutter="default", auto_range=False))["x_tool"]


def test_a_gutter_is_a_number_or_default(inputs):
    for bad in (-1, "auto"):
        done = subprocess.run([str(PAINT), str(page(inputs, "d02-x01-y01", y_gutter=bad)), "--dump-ranges"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert done.returncode == 1 and "y_gutter" in done.stdout + done.stderr


def test_data_that_lines_up_nowhere_is_dropped(inputs):
    # an eta table of the data against an ET histogram: no edge in common
    assert dump(page(inputs, "d01-x01-y01", data="d02-x01-y01"))["data_bins"] == 0
    assert dump(page(inputs, "d01-x01-y01", data="d01-x01-y01"))["data_bins"] > 0


def test_a_page_is_saved_in_every_format(inputs):
    config = page(inputs, "d01-x01-y01", data="d01-x01-y01", formats=["pdf", "png", "svg"], ratio=True,
                  logy=True, title="-3.5 < #eta < 3.5", x_label="E_{T} [GeV]", **LEGACY_PAGE)
    done = subprocess.run([str(PAINT), str(config)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    for fmt in ("pdf", "png", "svg"):
        assert (inputs["dir"] / f"d01-x01-y01.{fmt}").stat().st_size > 1000


@pytest.mark.parametrize(("y_range", "edge"), [
    (["default", 10_000], "top"),
    ([10_000, "default"], "bottom"),
])
def test_explicit_y_range_draws_clipped_overflow_marks_outside_the_frame(inputs, y_range, edge):
    config = page(inputs, "d02-x01-y01", formats=["svg"], auto_range=False, y_range=y_range)
    done = subprocess.run([str(PAINT), str(config)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr

    root = ET.parse(inputs["dir"] / "d02-x01-y01.svg").getroot()
    frame = next(node for node in root.iter() if node.tag.endswith("rect")
                 and node.get("fill") == "none" and node.get("stroke") == "black")
    top = float(frame.get("y"))
    bottom = top + float(frame.get("height"))
    markers = []
    for node in root.iter():
        if not node.tag.endswith("path") or node.get("stroke") not in {"#ee3311", "#3366ff"}:
            continue
        path = re.fullmatch(r"M([-+\d.eE]+),([-+\d.eE]+)h\s*([-+\d.eE]+)", node.get("d", ""))
        if path:
            y, width = float(path.group(2)), float(node.get("stroke-width", "0"))
            outside = y < top if edge == "top" else y > bottom
            if outside:
                markers.append((node.get("stroke"), y, width))
    assert len(markers) >= 2
    assert {colour for colour, _, _ in markers} == {"#ee3311", "#3366ff"}
    assert all(width < 4 for _, _, width in markers)
    gap = 2 * 72 / 300
    if edge == "top":
        assert all(top - y == pytest.approx(gap, abs=0.01) for _, y, _ in markers)
    else:
        assert all(y - bottom == pytest.approx(gap, abs=0.01) for _, y, _ in markers)


# ── x_range and y_range: explicit ends only, display only; overflow marks ───────────────────────

def small_page(where: Path, name: str, curves: list[Path], **keys) -> Path:
    document = {"page": {"name": name, "output": str(where / name), **keys},
                "curve": [{"file": str(c), "object": "photo_eic/d01-x01-y01", "label": c.stem} for c in curves]}
    path = where / f"{name}.toml"
    path.write_text(tomli_w.dumps(document), encoding="utf-8")
    return path


def paint(*args) -> subprocess.CompletedProcess:
    return subprocess.run([str(PAINT), *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace")


@pytest.mark.parametrize("name, values, edges, keys", [
    ("empty_log_y", [0.0, 0.0, 0.0, 0.0], (0.0, 1.0, 2.0, 3.0, 4.0), {"logy": True}),                # y from 0
    ("zero_mc_log_y", [0.0, 0.0], (0.0, 1.0, 2.0), {"logy": True, "y_gutter": 0.5}),
    ("log_x_from_0", [5.0, 1.0, 2.0, 3.0], (0.0, 1.0, 2.0, 3.0, 4.0), {"logx": True}),
])
def test_a_calculated_range_is_never_refused(scratch, name, values, edges, keys):
    """Only an axis with an explicit end is checked: these pages draw, and keep their statistics."""
    config = small_page(scratch, name, [v1_curve(scratch, name, values, edges=edges)], formats=["png"], **keys)
    done = paint(config, "--ranges")
    assert done.returncode == 0, done.stderr
    assert (scratch / f"{name}.png").is_file() and Path(f"{config}.stats.json").is_file()


@pytest.mark.parametrize("keys, axis", [
    ({"x_range": [5, "default"]}, "x_range"),                    # past the calculated maximum, 4
    ({"x_range": ["default", -1]}, "x_range"),
    ({"logx": True, "x_range": [0, 3]}, "x_range"),             # an explicit 0 on a log axis
    ({"logy": True, "y_range": [-1, 10]}, "y_range"),
    ({"y_range": ["default", -5]}, "y_range"),                   # below the calculated minimum, 0
])
def test_explicit_ranges_that_leave_nothing_are_the_pages_error(v1, keys, axis):
    where, curves = v1
    config = small_page(where, "refused", curves, **keys)
    for mode in ("--dump-ranges", "--ranges-only"):
        done = paint(config, mode)
        assert done.returncode == 1 and axis in done.stdout + done.stderr, (keys, mode)


def test_the_ranges_only_show_the_statistics_are_the_pages(v1):
    """x_range and y_range narrow no statistic: they are taken over the span auto-range and the gutters give."""
    where, curves = v1
    numbers = []
    for name, keys in (("whole", {}), ("narrow", {"x_range": [1.5, 2.5], "y_range": [0.5, 2]})):
        config = small_page(where, name, curves, auto_range=True, **keys)
        assert paint(config, "--ranges-only").returncode == 0
        numbers.append(json.loads(Path(f"{config}.stats.json").read_text(encoding="utf-8")))
        ranges = json.loads(Path(f"{config}.ranges.json").read_text(encoding="utf-8"))
        assert ranges["x"] == ([0, 4] if not keys else [1.5, 2.5])
    whole, narrow = numbers
    assert narrow["x"] == whole["x"] == [0, 4]
    assert narrow["curves"] == whole["curves"] and whole["curves"][1]["bins"] == 4      # all 4, though x_range holds none whole


def test_paints_ranges_are_what_mkhtml_is_handed(v1):
    """The handoff: Paint's --ranges, with explicit ends, read back as the yoda backend's plot block."""
    from runner import plot
    where, curves = v1
    config = small_page(where, "handed", curves, auto_range=True, x_range=["default", 3.5], y_range=[0.5, "default"])
    assert paint(config, "--ranges-only").returncode == 0
    ranges = json.loads(Path(f"{config}.ranges.json").read_text(encoding="utf-8"))
    assert ranges["x"] == [0, 3.5] and ranges["y"][0] == 0.5 and ranges["y"][1] > 5
    assert not ranges["x_tool"] and not ranges["y_tool"]
    page = plot.Page("handed", config, where / "handed", object="/photo_eic/d01-x01-y01",
                     document={"page": {"logx": False, "logy": False, "ratio": False}}, style=plot.base_style(),
                     ranges=ranges)
    block = plot.backend("yoda")._plot_block(page)
    assert "XMin=0\n" in block and "XMax=3.5\n" in block and "YMin=0.5\n" in block
    assert f"YMax={ranges['y'][1]:.10g}" in block


def svg_lines(svg: Path) -> tuple[list[tuple[float, float]], list[tuple[str, float, float, float, float]]]:
    """A page's frames, (top, bottom) from the top down, and its one-segment horizontal lines in colour:
    (colour, y, x, length, stroke width)."""
    root = ET.parse(svg).getroot()
    frames = sorted({(float(n.get("y")), float(n.get("y")) + float(n.get("height"))) for n in root.iter()
                     if n.tag.endswith("rect") and n.get("fill") == "none" and n.get("stroke") == "black"})
    lines = []
    for node in root.iter():
        found = re.fullmatch(r"M([-+\d.eE]+),([-+\d.eE]+)h\s*([-+\d.eE]+)", node.get("d", "")) if node.tag.endswith("path") else None
        if found and node.get("stroke") not in (None, "black", "#000000"):
            x, y, length = map(float, found.groups())
            lines.append((node.get("stroke"), y, x, length, float(node.get("stroke-width", "0"))))
    return frames, lines


GAP = 2 * 72 / 300                      # 2 px at the base style's 300 dpi, in the SVG's points
A, B = "#ee3311", "#3366ff"             # the palette's first two: curve a [5, 0, 0, 2], b [4, 0, 3, 1]


def marks_at(lines, y: float) -> list[tuple[str, float, float]]:
    return sorted((colour, x, length) for colour, at, x, length, _ in lines if at == pytest.approx(y, abs=0.01))


def test_curves_past_one_end_split_a_bin_the_nearest_first(v1):
    """Above 0.5: bin 1 b (3.5 past) then a (4.5), bin 3 b alone, bin 4 b (0.5) then a (1.5); bin 2 none."""
    where, curves = v1
    config = small_page(where, "split", curves, formats=["svg"], y_range=["default", 0.5])
    assert paint(config).returncode == 0
    frames, lines = svg_lines(where / "split.svg")
    (top, _), = frames
    marks = marks_at(lines, top - GAP)
    assert [c for c, _, _ in sorted(marks, key=lambda m: m[1])] == [B, A, B, B, A]
    halves, whole = [l for _, _, l in marks if l < 50], [l for _, _, l in marks if l > 50]
    assert len(halves) == 4 and len(whole) == 1 and all(2 * h == pytest.approx(whole[0], abs=0.01) for h in halves)
    assert all(width < 4 for _, y, _, _, width in lines if y == pytest.approx(top - GAP, abs=0.01))


def test_a_mark_covers_only_the_bins_part_within_x(v1):
    where, curves = v1
    config = small_page(where, "clipped", curves, formats=["svg"], y_range=["default", 0.5], x_range=[0.5, 4])
    assert paint(config).returncode == 0
    frames, lines = svg_lines(where / "clipped.svg")
    (top, _), = frames
    marks = sorted(marks_at(lines, top - GAP), key=lambda m: m[1])
    bin1 = marks[0][2] + marks[1][2]                              # bin 1 from 0.5: half a bin
    assert bin1 == pytest.approx(0.5 * marks[2][2], abs=0.02)      # bin 3, whole, b alone


def test_on_a_log_axis_an_empty_bin_gets_no_mark(v1):
    """Below 1.5 on log y: a's and b's empty bins are not marked, b's 1 in bin 4 is."""
    where, curves = v1
    config = small_page(where, "log", curves, formats=["svg"], logy=True, y_range=[1.5, "default"])
    assert paint(config).returncode == 0
    frames, lines = svg_lines(where / "log.svg")
    (_, bottom), = frames
    assert [c for c, _, _ in marks_at(lines, bottom + GAP)] == [B]


@pytest.mark.parametrize("gap, inside", [(0.0, True), (6.0, False)])
def test_with_a_joined_ratio_pad_the_lower_marks_are_inside_the_frame(v1, gap, inside):
    """Below 3.5 with a ratio pad: a mark where the pad leaves room for it, else 2 px inside the frame."""
    where, curves = v1
    config = small_page(where, f"ratio{gap:g}", curves, formats=["svg"], ratio=True, y_range=[3.5, "default"])
    document = tomllib.loads(config.read_text(encoding="utf-8"))
    document["style"] = {"ratio": {"gap": gap}}
    config.write_text(tomli_w.dumps(document), encoding="utf-8")
    assert paint(config).returncode == 0
    frames, lines = svg_lines(where / f"ratio{gap:g}.svg")
    (_, bottom), (ratio_top, _) = frames[0], frames[1]
    assert (ratio_top - bottom == pytest.approx(gap, abs=0.05))
    marks = marks_at(lines, bottom - GAP if inside else bottom + GAP)
    assert sorted(c for c, _, _ in marks) == sorted([A, B, B, A, A, B])      # bins 2, 3, 4: both curves each
    assert not marks_at(lines, bottom + GAP if inside else bottom - GAP)


def heat_map(where: Path, name: str, **keys) -> Path:
    yoda = pytest.importorskip("yoda")
    h = yoda.Histo2D(4, 0, 4, 3, 0, 3, "/photo_eic/d90-x01-y01")
    for i in range(60):
        h.fill(i % 4 + 0.5, i % 3 + 0.5, 1.0 + i % 5)
    source, target = where / "h2.yoda", where / "h2.root"
    if not target.exists():
        yoda.write([h], str(source))
        assert subprocess.run([str(YD2RT), str(source), str(target)], capture_output=True).returncode == 0
    document = {"page": {"name": name, "output": str(where / name), "heatmap": True, "formats": ["png"], **keys},
                "curve": [{"file": str(target), "object": "photo_eic/d90-x01-y01", "label": "h"}]}
    path = where / f"{name}.toml"
    path.write_text(tomli_w.dumps(document), encoding="utf-8")
    return path


@pytest.mark.parametrize("keys, refused", [
    ({}, ""),
    ({"x_range": [0.5, 2.5], "y_range": ["default", 2]}, ""),              # inside: widened to whole bins
    ({"x_range": [-3, 10]}, ""),                                            # past it: kept within it
    ({"x_range": [5, 9]}, "x_range"),                                       # misses it
    ({"y_range": ["default", -1]}, "y_range"),
    ({"logx": True, "x_range": [0, 2]}, "x_range"),
])
def test_a_heat_maps_range_is_checked_against_its_histogram(scratch, keys, refused):
    config = heat_map(scratch, "map", **keys)
    done = paint(config)
    if refused:
        assert done.returncode == 1 and refused in done.stdout + done.stderr
        assert ("misses the heat map" in done.stdout + done.stderr) == (keys == {"x_range": [5, 9]})
        assert not (scratch / "map.png").exists()
    else:
        assert done.returncode == 0, done.stderr
        assert (scratch / "map.png").is_file()
        (scratch / "map.png").unlink()
    assert paint(config, "--dump-ranges").stdout.strip() == '{"heatmap": true}'


def test_exit_codes(inputs):
    usage = subprocess.run([str(PAINT)], capture_output=True, text=True, encoding="utf-8")
    bad = inputs["dir"] / "bad.toml"
    bad.write_text("[page]\nname = 'x'\n", encoding="utf-8")                                   # no output, no curves
    missing = page(inputs, "d99-x01-y01")
    assert usage.returncode == 2
    assert subprocess.run([str(PAINT), str(bad)], capture_output=True).returncode == 1
    assert subprocess.run([str(PAINT), str(missing)], capture_output=True).returncode == 4


# ── v1's transform vectors (tests/python/plot/test_plot_pipeline.py at rework/v1-final) ────────

def v1_curve(where: Path, name: str, values, *, edges=(0.0, 1.0, 2.0, 3.0, 4.0), entries=None) -> Path:
    """A Rivet-shaped histogram, and its /RAW twin when `entries` is given, converted to ROOT."""
    yoda = pytest.importorskip("yoda")
    estimate = yoda.BinnedEstimate1D(list(edges), "/photo_eic/d01-x01-y01")
    for index, value in enumerate(values, start=1):
        estimate.bin(index).setVal(value)
        estimate.bin(index).setErr(math.sqrt(abs(value)) if value else 0.0)
    objects = [estimate]
    if entries is not None:
        raw = yoda.Histo1D(list(edges), "/RAW/photo_eic/d01-x01-y01")
        for index, count in enumerate(entries):
            for _ in range(count):
                raw.fill((edges[index] + edges[index + 1]) / 2, 1.0)
        objects.append(raw)
    source, target = where / f"{name}.yoda", where / f"{name}.root"
    yoda.write(objects, str(source))
    assert subprocess.run([str(YD2RT), str(source), str(target), "--keep-raw"], capture_output=True).returncode == 0
    return target


def v1_page(where: Path, curves: list[Path], *, data: Path | None = None, **keys) -> dict:
    keys = {"auto_range": True, **keys}             # v1's rule, stated: a page without it is ROOT's own range (V55)
    document = {"page": {"name": "v1", "output": str(where / "v1"), **keys},
                "curve": [{"file": str(c), "object": "photo_eic/d01-x01-y01", "label": c.stem,
                           **({"raw": "RAW/photo_eic/d01-x01-y01"} if keys.get("min_entries") else {})} for c in curves]}
    if data:
        document["data"] = {"file": str(data), "object": "photo_eic/d01-x01-y01", "label": "data"}
    path = where / f"v1.{len(list(where.glob('v1.*.toml')))}.toml"
    path.write_text(tomli_w.dumps(document), encoding="utf-8")
    return dump(path)


@pytest.fixture
def v1(scratch):
    """Two curves: bin 2 is empty in both, bin 3 only in one."""
    return scratch, [v1_curve(scratch, "a", [5.0, 0.0, 0.0, 2.0], entries=[50, 0, 0, 20]),
                     v1_curve(scratch, "b", [4.0, 0.0, 3.0, 1.0], entries=[40, 0, 3, 10])]


def test_v1_a_bin_empty_in_every_curve_is_voided(v1):
    where, curves = v1
    assert v1_page(where, curves, void_empty=True)["voided"] == [2]


def test_v1_a_bin_too_few_entries_went_into_is_voided(v1):
    where, curves = v1
    assert v1_page(where, curves, void_empty=True, min_entries=25)["voided"] == [2, 3, 4]


def test_v1_voiding_is_a_no_op_when_nothing_is_asked_for(v1):
    where, curves = v1
    assert v1_page(where, curves)["voided"] == []


def test_v1_auto_range_clips_to_the_filled_bins(v1):
    where, curves = v1
    assert v1_page(where, curves, range_pad=0)["x"] == [0, 4]


def test_v1_auto_range_pads_by_whole_bins(scratch):
    middle = [v1_curve(scratch, "c", [0.0, 7.0, 0.0, 0.0])]
    assert v1_page(scratch, middle, range_pad=1)["x"] == [0, 3]
    assert v1_page(scratch, middle, range_pad=0)["x"] == [1, 2]


def test_v1_nothing_filled_leaves_the_full_range(scratch):
    empty = [v1_curve(scratch, "e", [0.0, 0.0], edges=(0.0, 1.0, 2.0))]
    assert v1_page(scratch, empty)["x"] == [0, 2]


def test_v1_data_is_trimmed_to_its_longest_aligned_run(scratch):
    mc = [v1_curve(scratch, "mc", [1.0, 1.0, 1.0, 1.0])]
    aligned = v1_curve(scratch, "ref", [1.0, 2.0, 3.0], edges=(0.5, 1.0, 2.0, 3.0))
    unaligned = v1_curve(scratch, "bad", [1.0, 2.0], edges=(0.1, 0.9, 1.7))
    assert v1_page(scratch, mc, data=aligned)["data_bins"] == 2           # [1, 2, 3]: the 0.5 edge goes
    assert v1_page(scratch, mc, data=unaligned)["data_bins"] == 0


# ── the style (Style.hh, src/Apps/Paint/base.toml) ─────────────────────────────────────────

def dump_style(path: Path | None = None, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(PAINT), *([str(path)] if path else []), "--dump-style", *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_the_base_style_is_base_toml():
    done = dump_style()
    assert done.returncode == 0, done.stderr
    assert tomllib.loads(done.stdout) == tomllib.loads((REPO / "src/Apps/Paint/base.toml").read_text(encoding="utf-8"))


def test_a_page_style_merges_over_the_base_and_is_checked(inputs):
    config = page(inputs, "d01-x01-y01", formats=["png"])
    document = tomllib.loads(config.read_text(encoding="utf-8"))
    document["style"] = {"page": {"dpi": 100}, "legend": {"position": [0.4, 0.9]}}
    config.write_text(tomli_w.dumps(document), encoding="utf-8")
    merged = tomllib.loads(dump_style(config).stdout)
    assert merged["page"]["dpi"] == 100 and merged["legend"]["position"] == [0.4, 0.9]
    assert merged["text"] == tomllib.loads((REPO / "src/Apps/Paint/base.toml").read_text(encoding="utf-8"))["text"]
    done = subprocess.run([str(PAINT), str(config)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    Image = pytest.importorskip("PIL.Image")
    assert Image.open(inputs["dir"] / "d01-x01-y01.png").size == (467, 421)   # size × dpi
    for bad, message in (({"legend": {"place": 1}}, "legend.place"), ({"page": {"dpi": "x"}}, "page.dpi"),
                         ({"curves": {"errors": "dots"}}, "curves.errors")):
        document["style"] = bad
        config.write_text(tomli_w.dumps(document), encoding="utf-8")
        done = subprocess.run([str(PAINT), str(config)], capture_output=True, text=True, encoding="utf-8")
        assert done.returncode == 1 and message in done.stderr + done.stdout


def test_many_pages_in_one_paint_each_with_its_outcome_and_ranges(inputs):
    """V64: one ROOT for many pages; a bad page does not stop the rest; --ranges writes what --dump-ranges prints."""
    good = page(inputs, "d01-x01-y01", **LEGACY_PAGE)
    other = page(inputs, "d02-x01-y01", **LEGACY_PAGE)
    bad = inputs["dir"] / "broken.toml"
    bad.write_text('[page]\nname = "x"\noutput = "/nonexistent/dir/x"\n', encoding="utf-8")   # no [[curve]]
    done = subprocess.run([str(PAINT), str(good), str(bad), str(other), "--ranges"], capture_output=True, text=True,
                          encoding="utf-8")
    lines = [json.loads(l) for l in done.stdout.splitlines() if l.startswith("{")]
    assert done.returncode == 1 and [l["ok"] for l in lines] == [True, False, True]
    assert "curve" in lines[1]["error"]
    for config in (good, other):
        written = json.loads(Path(str(config) + ".ranges.json").read_text(encoding="utf-8"))
        assert written == dump(config)


def test_a_curve_may_have_its_own_look(inputs):
    """V67: a curve's style (colour, line, width) is drawn; an unknown line is the page's error."""
    config = page(inputs, "d01-x01-y01")
    document = tomllib.loads(config.read_text(encoding="utf-8"))
    document["curve"][0]["style"] = {"colour": "#109618", "line": "dashed", "width": 2.0}
    config.write_text(tomli_w.dumps(document), encoding="utf-8")
    assert subprocess.run([str(PAINT), str(config)], capture_output=True).returncode == 0
    document["curve"][1]["style"] = {"line": "wavy"}
    config.write_text(tomli_w.dumps(document), encoding="utf-8")
    done = subprocess.run([str(PAINT), str(config)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 1 and "style.line" in done.stdout + done.stderr


def test_normalise_scales_every_curve_to_unit_area(v1):
    """V68: Σ y·Δx = 1 per curve over the drawn bins; a: 5/7 at most, b: 4/8."""
    where, curves = v1
    assert v1_page(where, curves)["largest"] == pytest.approx(5.0)
    assert v1_page(where, curves, normalise="area")["largest"] == pytest.approx(5.0 / 7.0)
    assert v1_page(where, curves, normalise=False)["largest"] == pytest.approx(5.0)


def test_normalise_is_area_or_false(v1):
    where, curves = v1
    path = where / "bad_normalise.toml"
    path.write_text(tomli_w.dumps({"page": {"name": "v1", "output": str(where / "v1"), "normalise": "peak"},
                                   "curve": [{"file": str(curves[0]), "object": "photo_eic/d01-x01-y01", "label": "a"}]}), encoding="utf-8")
    done = subprocess.run([str(PAINT), str(path), "--dump-ranges"], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 1 and "normalise" in done.stdout + done.stderr


def test_a_band_curve_spans_its_members(v1):
    """V69: a curve's band members widen the range to their envelope; a member of other bins is no band."""
    where, (a, b) = v1
    alone = v1_page(where, [b])
    path = where / "band.toml"
    document = {"page": {"name": "v1", "output": str(where / "band"), "auto_range": True},
                "curve": [{"file": str(b), "object": "photo_eic/d01-x01-y01", "label": "b",
                           "band": [{"file": str(a), "object": "photo_eic/d01-x01-y01"}]}]}
    path.write_text(tomli_w.dumps(document), encoding="utf-8")
    assert alone["largest"] == pytest.approx(4.0) and dump(path)["largest"] == pytest.approx(5.0)
    assert subprocess.run([str(PAINT), str(path)], capture_output=True).returncode == 0
