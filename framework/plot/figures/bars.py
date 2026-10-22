"""statistics.csv as bar graphs (V162): results/…/plots/statistics/<cell>/<object>.<fmt>, one per drawn page, and
statistics/summary.<fmt>, each point's mean χ²/ndf over its pages. Matplotlib (the conda base's), Agg.

A page's image is three panels side by side, one bar per curve in the page's order, each statistic on its own
axis (no two scales on one): χ²/ndf and |Δ|/ref against the page's reference, and the area. One series, one
colour; the values at the bars' tips, in text ink; the reference curve (a page without data) is named, not
drawn. Rows are plot.statistics_of's (runner/plot.py).
"""

from __future__ import annotations

import math
from pathlib import Path

SERIES = "#2a78d6"            # one series: the palette's first categorical slot
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
PANELS = (("chi2_ndf", r"$\chi^{2}$/ndf"), ("rel_abs_area", r"$|\Delta|$ / reference"), ("area", "area"))


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _shown(value: float) -> str:
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:.3g}"


def _label(text: str) -> str:
    """A curve label as mathtext reads it: its $…$ kept, unbalanced dollars dropped."""
    from runner.labels import mathtext
    try:
        return mathtext(text)
    except Exception:                                   # a label mathtext cannot take is drawn as written
        return text.replace("$", "")


def _style(ax, labels: list[str]) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", colors=MUTED, labelsize=8, length=0)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylim(len(labels) - 0.5, -0.5)               # the page's first curve on top


def _bars(ax, values: list, notes: list[str]) -> None:
    """Thin bars from one baseline, each value at its tip; a missing value says why."""
    finite = [v for v in values if _finite(v)]
    top = max(finite + [0.0]) or 1.0
    for i, (value, note) in enumerate(zip(values, notes)):
        if _finite(value):
            ax.barh(i, value, height=0.55, color=SERIES, edgecolor=SURFACE, linewidth=2)
            ax.text(value + 0.015 * top, i, _shown(value), va="center", ha="left", color=INK, fontsize=8)
        else:
            ax.text(0.015 * top, i, note, va="center", ha="left", color=MUTED, fontsize=8, style="italic")
    ax.set_xlim(0, top * 1.22)


def page(rows: list[dict], target: Path, formats: list[str], title: str) -> list[Path]:
    """One page's statistics: three panels, a bar per curve."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = [_label(r["curve"]) for r in rows]
    height = 1.2 + 0.32 * len(rows)
    fig, axes = plt.subplots(1, len(PANELS), figsize=(11, height), sharey=True, facecolor=SURFACE)
    for k, (ax, (key, name)) in enumerate(zip(axes, PANELS)):
        notes = ["reference" if r["is_reference"] and key != "area" else "no bins compared" for r in rows]
        values = [None if (r["is_reference"] and key != "area") else r[key] for r in rows]
        _style(ax, labels)
        _bars(ax, values, notes)
        ax.set_title(name, color=INK, fontsize=10, loc="left")
        if k == 0:
            ax.set_yticks(range(len(labels)), labels, color=INK, fontsize=9)
    reference = rows[0]["reference"] if rows else ""
    fig.suptitle(f"{title}  ·  against {_label(reference)}", color=MUTED, fontsize=9, x=0.01, ha="left")
    fig.tight_layout()
    written = []
    target.parent.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        path = target.with_suffix(f".{fmt}")
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        written.append(path)
    plt.close(fig)
    return written


def summary(rows: list[dict], target: Path, formats: list[str]) -> list[Path]:
    """Each point's mean χ²/ndf over the pages where it was compared, best first."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    by: dict[str, list[float]] = {}
    for r in rows:
        if not r["is_reference"] and _finite(r["chi2_ndf"]):
            by.setdefault(r["point"], []).append(r["chi2_ndf"])
    if not by:
        return []
    ranked = sorted(((sum(v) / len(v), name, len(v)) for name, v in by.items()))
    fig, ax = plt.subplots(figsize=(8, 1.2 + 0.3 * len(ranked)), facecolor=SURFACE)
    names = [f"{name}  ({n})" for _, name, n in ranked]
    _style(ax, names)
    _bars(ax, [mean for mean, _, _ in ranked], ["" for _ in ranked])
    ax.set_yticks(range(len(names)), names, color=INK, fontsize=9)
    ax.set_title(r"mean $\chi^{2}$/ndf over its pages (pages compared)", color=INK, fontsize=10, loc="left")
    fig.tight_layout()
    written = []
    target.parent.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        path = target.with_suffix(f".{fmt}")
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        written.append(path)
    plt.close(fig)
    return written


def draw(pages: list[tuple[str, list[dict]]], folder: Path, formats: list[str]) -> int:
    """Every page's image, then the summary, into `folder`; the number of images."""
    formats = [f for f in formats if f in ("png", "pdf", "svg")] or ["png"]
    made = 0
    for name, rows in pages:
        if rows:
            made += bool(page(rows, folder / name, formats, name))
    made += bool(summary([r for _, rows in pages for r in rows], folder / "summary", formats))
    return made
