"""framework/plot/figures/layout.py — figures laid out in a grid: a sheet's pages (V89), and the LaTeX a report's grids
are placed with (`picture`, `tex`, `pdflatex`).

One PDF, drawn by pdflatex: each panel (a page's PDF, or a PNG) placed in its cell by graphicx, vector as
it is, with an optional label above it and an optional title above the grid. The PNG is that PDF
rendered by pdftoppm, so the two are one picture.

* `tile(files, target, columns)`: a sheet. The pages at their own size, `columns` of them wide.

A page's size is the size it shows (a PDF's rotation applied). Errors are ValueError, with what is wrong.
"""

from __future__ import annotations

import math
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

TILED = ("pdf", "png")

PNG_DPI = 300                                # a PNG panel's resolution, when it says none (Paint's, base.toml)

_SPECIALS = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "{": r"\{",
             "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def tex(text: str) -> str:
    """Text for LaTeX: its specials escaped, `$…$` kept as math (an odd `$` is escaped too)."""
    parts = text.split("$")
    if len(parts) % 2 == 0:                  # an odd count of $: no math, all text
        parts = [text.replace("$", "\0")]
    out = []
    for number, part in enumerate(parts):
        if number % 2:
            out.append(f"${part}$")
        else:
            out.append("".join(_SPECIALS.get(c, c) for c in part).replace("\0", r"\$"))
    return "".join(out)


def _pdf_size(info: str) -> tuple[float, float]:
    """pdfinfo's text → the page's shown (width, height) in pt: its size, turned by its rotation."""
    size = re.search(r"Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", info)
    if not size:
        raise ValueError("pdfinfo gave no page size")
    w, h = float(size[1]), float(size[2])
    turned = re.search(r"Page rot:\s+(-?\d+)", info)
    return (h, w) if turned and int(turned[1]) % 180 else (w, h)


def _png_size(path: Path) -> tuple[float, float]:
    """A PNG's size in pt, from its header and its pHYs resolution (else PNG_DPI)."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name} is not a PNG")
    w, h = struct.unpack(">II", data[16:24])
    dpi_x = dpi_y = PNG_DPI
    at = data.find(b"pHYs")
    if at > 0:
        px, py, unit = struct.unpack(">IIB", data[at + 4:at + 13])
        if unit == 1 and px and py:                          # pixels per metre
            dpi_x, dpi_y = px * 0.0254, py * 0.0254
    return w * 72.0 / dpi_x, h * 72.0 / dpi_y


def size_of(path: Path) -> tuple[float, float]:
    """The size a panel shows, (width, height) in pt."""
    if path.suffix.lower() == ".png":
        return _png_size(path)
    if not shutil.which("pdfinfo"):
        raise ValueError("a page's size is read by pdfinfo (poppler), which is not on PATH")
    done = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise ValueError(f"pdfinfo cannot read {path.name}: {done.stderr.strip()}")
    return _pdf_size(done.stdout)


def picture(files: list[str], labels: list[str], box: tuple[float, float], columns: int, rows: int, cw: float,
            ch: float, label: float, title: str, title_h: float, gap: float, options: list[str] | None = None,
            style: str = "") -> list[str]:
    """A grid as a LaTeX picture's lines (sheets and the report's grids): each file (as the
    source names it) in its cell, aspect kept and centred, its label above it, the title on top. Units bp.
    `options`: each file's further \\includegraphics keys (`page=2`); `style`: the labels' font, a
    command of the document's (a report's \\hdPanel), else sans at a size from `label`."""
    width, height = box
    label_pt = min(12.0, 0.75 * label) if label else 0.0
    title_pt = min(18.0, 0.7 * title_h) if title_h else 0.0
    lines = []
    for number, (name, text) in enumerate(zip(files, labels)):
        column, row = number % columns, number // columns
        x = column * (cw + gap)
        top = height - title_h - row * (ch + label + gap)
        more = f",{options[number]}" if options and options[number] else ""
        lines.append(rf"\put({x:.2f},{top - label - ch:.2f}){{\makebox({cw:.2f},{ch:.2f}){{"
                     rf"\includegraphics[width={cw:.2f}bp,height={ch:.2f}bp,keepaspectratio{more}]{{{name}}}}}}}")
        if label and text:
            font = style or rf"\fontsize{{{label_pt:.1f}}}{{{label_pt * 1.2:.1f}}}\selectfont\sffamily"
            lines.append(rf"\put({x:.2f},{top - label:.2f}){{\makebox({cw:.2f},{label:.2f})"
                         rf"{{{font} {tex(text)}}}}}")
    if title_h and title:
        lines.append(rf"\put(0,{height - title_h:.2f}){{\makebox({width:.2f},{title_h:.2f})"
                     rf"{{\fontsize{{{title_pt:.1f}}}{{{title_pt * 1.2:.1f}}}\selectfont\sffamily {tex(title)}}}}}")
    return lines


def pdflatex(source: Path, what: str, runs: int = 1) -> Path:
    """`source` (.tex) made into its PDF by pdflatex in its own folder, `runs` times (2: a contents' pages); the
    PDF. A failure is a ValueError naming `what`, with the log's first error."""
    if not shutil.which("pdflatex"):
        raise ValueError("a layout's PDF is made by pdflatex, which is not on PATH")
    made = source.with_suffix(".pdf")
    for _ in range(runs):
        done = subprocess.run(["pdflatex", "-interaction=batchmode", "-halt-on-error", source.name],
                              cwd=source.parent, capture_output=True, text=True, encoding="utf-8")
        if done.returncode != 0 or not made.is_file():
            log = source.with_suffix(".log")
            text = log.read_text(errors="replace", encoding="utf-8") if log.is_file() else done.stdout
            errors = [line for line in text.splitlines() if line.startswith("!")]
            raise ValueError(f"pdflatex could not lay out {what}: "
                             f"{errors[0] if errors else (text.strip().splitlines() or [done.returncode])[-1]}")
    return made


def _draw(panels: list[tuple[Path, str]], target: Path, box: tuple[float, float], columns: int, rows: int,
          cw: float, ch: float, label: float, title: str, title_h: float, gap: float) -> None:
    """The picture: each panel in its cell (aspect kept, centred), its label above, the title on top."""
    if not shutil.which("pdflatex"):
        raise ValueError("a layout's PDF is made by pdflatex, which is not on PATH")
    width, height = box
    with tempfile.TemporaryDirectory() as work:
        names = []
        for number, (path, _) in enumerate(panels):
            linked = Path(work) / f"p{number}{path.suffix.lower()}"
            linked.symlink_to(path.resolve())
            names.append(linked.name)
        lines = picture(names, [text for _, text in panels], box, columns, rows, cw, ch, label, title, title_h, gap)
        source = Path(work) / "layout.tex"
        source.write_text(
            "\\documentclass[margin=0pt]{standalone}\n\\usepackage[T1]{fontenc}\n\\usepackage{lmodern}\n\\usepackage{graphicx}\n"
            "\\begin{document}\n\\setlength{\\unitlength}{1bp}%\n"
            f"\\begin{{picture}}({width:.2f},{height:.2f})\n" + "\n".join(lines) + "\n\\end{picture}\n\\end{document}\n",
            encoding="utf-8")
        made = pdflatex(source, target.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(made, target)


def png(pdf: Path, target: Path, dpi: float = 200, pixels: tuple[int, int] | None = None) -> None:
    """`target` (.png): the PDF's page rendered by pdftoppm, at a resolution or to a pixel size."""
    if not shutil.which("pdftoppm"):
        raise ValueError("a layout's PNG is rendered by pdftoppm (poppler), which is not on PATH")
    scale = ["-scale-to-x", str(pixels[0]), "-scale-to-y", str(pixels[1])] if pixels else ["-r", f"{dpi:g}"]
    done = subprocess.run(["pdftoppm", "-png", "-singlefile", *scale, str(pdf), str(target)[:-len(".png")]],
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0 or not target.is_file():
        raise ValueError(f"pdftoppm could not render {pdf.name}: {done.stderr.strip() or done.returncode}")


def tile(files: dict[str, list[Path]], target: Path, columns: int) -> list[str]:
    """A sheet: `files` is format → the pages' files, in order. Each page shown by its PDF (else its PNG),
    in cells of the largest page's size, `columns` wide, into `<target>.pdf`; `<target>.png` is that PDF
    rendered, at the pages' own PNG size when every page has one. The formats made: none when a page
    has neither file."""
    count = max((len(paths) for paths in files.values()), default=0)
    pdfs, pngs = files.get("pdf", []), files.get("png", [])
    pages = []
    for number in range(count):
        found = [p for p in (pdfs[number] if number < len(pdfs) else None,
                             pngs[number] if number < len(pngs) else None) if p is not None and p.is_file()]
        if not found:
            return []
        pages.append(found[0])
    if not pages:
        return []
    sizes = [size_of(p) for p in pages]
    cw, ch = max(w for w, _ in sizes), max(h for _, h in sizes)
    rows = math.ceil(len(pages) / columns)
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf = target.with_name(f"{target.name}.pdf")
    _draw([(p, "") for p in pages], pdf, (cw * columns, ch * rows), columns, rows, cw, ch, 0.0, "", 0.0, 0.0)
    pixels = None
    if len(pngs) == count and all(p.is_file() for p in pngs):  # the pages' own PNG size, as V89 pasted them
        heads = [struct.unpack(">II", p.read_bytes()[16:24]) for p in pngs]
        pixels = (columns * max(w for w, _ in heads), rows * max(h for _, h in heads))
    png(pdf, target.with_name(f"{target.name}.png"), PNG_DPI, pixels)
    return ["pdf", "png"]
