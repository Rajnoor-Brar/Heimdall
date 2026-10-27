"""framework/plot/figures/layout.py (V102): panels laid out in a grid, as one PDF by pdflatex and its PNG
rendered from it by pdftoppm: a sheet's tiling (V89), and the text and pictures a report's LaTeX takes. Panels are
made here by PIL, in tmp_path."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from runner import plugins

REPO = Path(__file__).resolve().parents[2]
TOOLS = all(shutil.which(t) for t in ("pdflatex", "pdftoppm", "pdfinfo"))
needs_tools = pytest.mark.skipif(not TOOLS, reason="pdflatex and poppler (pdftoppm, pdfinfo) lay out the figures")


@pytest.fixture(scope="module")
def layout():
    return plugins.load(REPO / "framework" / "plot" / "figures" / "layout.py", "layout")


def page(path: Path, size=(336, 303), colour="white") -> Path:
    """A panel: a PDF of `size` bp, or a PNG of size × 300/72 pixels at 300 dpi."""
    from PIL import Image
    if path.suffix == ".pdf":
        Image.new("RGB", size, colour).save(path, "PDF", resolution=72)
    else:
        Image.new("RGB", (round(size[0] * 300 / 72), round(size[1] * 300 / 72)), colour).save(path, dpi=(300, 300))
    return path


def pdf_size(path: Path) -> tuple[float, float]:
    info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, encoding="utf-8").stdout
    w, h = info.split("Page size:")[1].split("pts")[0].split("x")
    return float(w), float(h)


def test_text_is_escaped_for_latex_and_math_kept(layout):
    assert layout.tex("d01_x01 10% & #2") == r"d01\_x01 10\% \& \#2"
    assert layout.tex(r"$\sqrt{s}$ = 63.2 GeV") == r"$\sqrt{s}$ = 63.2 GeV"
    assert layout.tex("costs $5") == r"costs \$5"                          # one $ is not math


def test_a_page_shows_its_rotation(layout):
    upright = "Page size:       336.24 x 303.12 pts\nPage rot:        0\n"
    turned = "Page size:       303 x 336 pts\nPage rot:        90\n"
    assert layout._pdf_size(upright) == (336.24, 303.12)
    assert layout._pdf_size(turned) == (336.0, 303.0)


@needs_tools
def test_a_sheet_tiles_pages_at_their_own_size(layout, tmp_path):
    pdfs = [page(tmp_path / f"d{i}.pdf") for i in range(3)]
    pngs = [page(tmp_path / f"d{i}.png") for i in range(3)]
    assert layout.tile({"pdf": pdfs, "png": pngs}, tmp_path / "sheets" / "grid", 2) == ["pdf", "png"]
    w, h = pdf_size(tmp_path / "sheets" / "grid.pdf")
    assert abs(w - 2 * 336) < 0.5 and abs(h - 2 * 303) < 0.5
    from PIL import Image
    one = Image.open(pngs[0]).size
    assert Image.open(tmp_path / "sheets" / "grid.png").size == (2 * one[0], 2 * one[1])
    # PDFs alone: the PNG is still made, rendered at Paint's 300 dpi (V102); no page needs a PNG
    assert layout.tile({"pdf": pdfs}, tmp_path / "pdf_only", 3) == ["pdf", "png"]
    made = Image.open(tmp_path / "pdf_only.png").size
    assert abs(made[0] - 3 * 336 * 300 / 72) <= 1 and abs(made[1] - 303 * 300 / 72) <= 1   # pdftoppm rounds
    assert layout.tile({"pdf": [pdfs[0], tmp_path / "gone.pdf"]}, tmp_path / "none", 2) == []
