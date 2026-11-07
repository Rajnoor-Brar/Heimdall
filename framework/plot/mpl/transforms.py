"""framework/plot/mpl/transforms.py — what the mpl backend does to YODA objects and settings before it draws.

doc:plot-backends. The page's curves get their voided bins, their unit area and their band envelopes; the
reference is cut to the bins Paint aligned; the ratio pad gets Paint's window; the page's settings are
written as the `.plot` block rivet reads (`_plot_block`); `validate` is the backend's limits (mkhtml's, the
look the pages keep until verified). Loaded by backend.py by path (backends are plugins), so it imports only
what a plugin may. Moved from the retired yoda backend, unchanged but for the name in its messages.
"""

from __future__ import annotations

import math
import re
import tomllib
from pathlib import Path

from runner.errors import HeimdallError
from runner.hepfiles import base_path
from runner.labels import canonical, mathtext

_SPEC = tomllib.loads((Path(__file__).with_name("backend.toml")).read_text(encoding="utf-8"))
LEGEND = _SPEC["legend"]
HONOURED = {tuple(key.split(".")) for key in _SPEC["style"]["honoured"]}         # style keys mkhtml can follow


def validate(settings: dict, beside_root: bool = False, curve_styles: list[dict] = ()) -> None:
    hint = 'the mpl backend keeps rivet-mkhtml\'s look; drop the key, or use backend = "root"'
    for look in curve_styles:                         # V67: matplotlib takes #rrggbb, not ROOT's names
        colour = look.get("colour")
        if colour is not None and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(colour)):
            raise HeimdallError(f"the mpl backend cannot draw the curve colour {colour!r}", where="[quantities].styles",
                           hint='write it as "#rrggbb", which both backends draw')
    if "root_style" in settings and not beside_root:
        raise HeimdallError('[plot].root_style cannot be honoured by backend = "mpl"', where="[plot].root_style", hint=hint)
    layers = [("[plot.style]", settings.get("style", {}))] + [
        (f'[plot.figures.{key}].style', table.get("style", {})) for key, table in settings.get("figures", {}).items()]
    for where, layer in layers:
        for table, keys in layer.items():
            for key, value in keys.items() if isinstance(keys, dict) else [(None, keys)]:
                if value == "default":                  # sets nothing, so there is nothing to honour
                    continue
                placed = (table, key) == ("legend", "position") and (not isinstance(value, str) or value not in LEGEND)
                if placed or (not beside_root and (table, key) not in HONOURED):
                    name = f"{table}.{key}" if key else table
                    raise HeimdallError(f'{where} {name} cannot be honoured by backend = "mpl"', where=where,
                                   hint=hint + " (only legend.position, text.legend, text.header and ratio.divisions, range and limits carry over)")


def _void(estimate, voided: list, source: Path) -> bool:
    if "Estimate" not in estimate.type():
        raise HeimdallError(f"cannot void bins of {estimate.path()}, a {estimate.type()}", where=str(source))
    for index in voided:
        estimate.bin(index).setVal(float("nan"))
        estimate.bin(index).rmErrs()
    return True


def _envelope(estimate, members: list) -> bool:
    """V69: a band curve's errors become its members' min–max envelope around it, which mkhtml draws as
    the curve's error band (ErrorBand=1), as Paint draws its envelope."""
    for i in range(1, estimate.numBins() + 1):
        b = estimate.bin(i)
        values = [b.val()] + [m.bin(i).val() for m in members]
        b.rmErrs()
        if all(math.isfinite(v) for v in values):
            b.setErr((min(values) - b.val(), max(values) - b.val()))
    return True


def _normalise(estimate) -> bool:
    """V68: unit area, Σ value·width over the finite bins (Paint's normalise); every error scaled with it."""
    bins = [estimate.bin(i) for i in range(1, estimate.numBins() + 1)]
    area = sum(b.val() * (b.xMax() - b.xMin()) for b in bins if math.isfinite(b.val()))
    if not (area > 0 and math.isfinite(area)):
        return False
    for b in bins:
        errors = {name: b.errDownUp(name) for name in b.sources()}
        b.setVal(b.val() / area)
        for name, (down, up) in errors.items():
            b.setErr((down / area, up / area), name)
    return True


def _reference(yoda, page):
    """The mapped reference object, cut to the run of bins Paint aligned to the MC edges (mkhtml's
    ratio needs every reference edge to be an MC edge), renamed /REF/<analysis>/<object>."""
    source = yoda.read(str(page.data[0]))[page.data[1]]
    lo, hi = page.ranges["data_x"]
    keep = [i for i in range(1, source.numBins() + 1)
            if source.bin(i).xMin() >= lo - 1e-9 * abs(lo) and source.bin(i).xMax() <= hi + 1e-9 * abs(hi)]
    edges = [source.bin(i).xMin() for i in keep] + [source.bin(keep[-1]).xMax()]
    out = yoda.BinnedEstimate1D(edges, "/REF" + base_path(page.object))
    for k, i in enumerate(keep, start=1):
        out.bin(k).setVal(source.bin(i).val())
        for name in source.bin(i).sources():
            out.bin(k).setErr(source.bin(i).errDownUp(name), name)
    if page.document["page"].get("normalise") == "area":
        _normalise(out)
    return out


def _bins(obj) -> list[tuple[float, float, float, float]]:
    """(x low, x high, value, error) per bin of a histogram (as drawn: per unit x) or an estimate."""
    estimate = obj.mkEstimate() if hasattr(obj, "mkEstimate") else obj
    out = []
    for i in range(1, estimate.numBins() + 1):
        b = estimate.bin(i)
        try:
            error = b.totalErrAvg()
        except Exception:                        # an estimate with no error source
            error = 0.0
        out.append((b.xMin(), b.xMax(), b.val(), error))
    return out


def ratio_window(curves: list, reference, x: tuple, ratio_style: dict) -> tuple[float, float]:
    """Paint's rule for the ratio pad (Draw.hh ratioRange), so both backends show the same window:
    at least `range`, widened to every ratio drawn (0.9 × (r − err), 1.1 × (r + err)) on bins in the
    x range, never past `limits` (V48). `curves` and `reference` are lists of `_bins`."""
    lo, hi = ratio_style["range"]
    by_edges = {(round(a, 9), round(b, 9)): (v, e) for a, b, v, e in reference}
    for curve in curves:
        for a, b, value, error in curve:
            ref = by_edges.get((round(a, 9), round(b, 9)))
            if ref is None or not ref[0] or not (b > x[0] and a < x[1]):
                continue
            r, err = value / ref[0], error / abs(ref[0])
            if math.isfinite(r):
                lo, hi = min(lo, 0.9 * (r - err)), max(hi, 1.1 * (r + err))
    limits = ratio_style["limits"]
    return max(lo, limits[0]), min(hi, limits[1])


def _plot_block(page, window: tuple[float, float] | None = None) -> str:
    settings = page.document["page"]
    (xlo, xhi), (ylo, yhi) = page.ranges["x"], page.ranges["y"]
    keys = {"XMin": f"{xlo:.10g}", "XMax": f"{xhi:.10g}", "YMin": f"{ylo:.10g}", "YMax": f"{yhi:.10g}",
            "LogX": str(int(settings["logx"])), "LogY": str(int(settings["logy"])),
            "RatioPlot": str(int(settings["ratio"])), **LEGEND.get(page.style["legend"]["position"], LEGEND["top-right"]),
            # mkhtml writes `plt.rcParams['legend.fontsize'] = <value>` into the page's script as given, so
            # the title's size rides along: matplotlib sizes a legend title from legend.title_fontsize,
            # else from font.size, never from the entries' size (V50)
            "LegendFontSize": f"{page.style['text']['legend']:g}; "
                              f"plt.rcParams['legend.title_fontsize'] = {page.style['text']['header']:g}"}
    if window and settings["ratio"]:
        top = window[1] - 1e-4 * (window[1] - window[0])     # as mkhtml's 1.4999: no tick label at the pad's top
        keys["RatioPlotYMin"], keys["RatioPlotYMax"] = f"{window[0]:.6g}", f"{top:.6g}"
    keys["Title"] = ""                                 # the titles are ours, drawn by backend.py's _titles (V51)
    overlay = getattr(page, "overlay", "")
    from runner.labels import labels_of, lines_of, macros
    own = labels_of(page.object)
    # a text that is not the .plot's as written: an override, an overlay's (its path has no .plot of its
    # own), or the .plot's own with its placeholders filled (V66)
    for key, native in (("x_label", "XLabel"), ("y_label", "YLabel"), ("legend_header", "LegendTitle")):
        if overlay or settings.get(key, "") != canonical(own.get(native, "")):
            keys[native] = mathtext(settings.get(key, ""))
    for native, text in own.items():  # mkhtml draws each line apart: close math per line (V47)
        if native in ("Title", "LegendTitle", "XLabel", "YLabel") and native not in keys:   # and our macros (V48)
            fixed = "\\newline".join(lines_of(macros(text)))
            if fixed != text:
                keys[native] = fixed
    if settings["logy"] and not ylo > 0:
        del keys["YMin"]
    for axis in ("x", "y"):                  # no gutter: the range is mkhtml's to choose, as it is ROOT's for Paint
        if page.ranges.get(f"{axis}_tool"):
            keys.pop(f"{axis.upper()}Min", None), keys.pop(f"{axis.upper()}Max", None)
    body = "".join(f"{k}={v}\n" for k, v in keys.items() if not (isinstance(v, str) and v in ("nan", "inf")))
    return f"# BEGIN PLOT {base_path(page.object)}\n{body}# END PLOT\n"


def _step(width: float) -> float:
    """The smallest 1, 2 or 5 × 10^k at least `width`: ROOT's choice for at most n divisions."""
    power = 10.0 ** math.floor(math.log10(width))
    return next(m * power for m in (1, 2, 5, 10) if m * power >= width * (1 - 1e-9))
