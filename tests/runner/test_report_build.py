"""runner/report.py's build (V208): figures/ copied as drawn, stats/ drawn from statistics.csv, report.tex
naming only its own folder's files, report.pdf on A4, index.html; a rebuild makes nothing again. Pages are PDFs
(and PNGs) made by PIL in a tmp_path results tree, with a statistics.csv beside them."""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from runner import report, statstable
from runner.errors import HeimdallError

TOOLS = all(shutil.which(t) for t in ("pdflatex", "pdftoppm", "pdfinfo", "pdftotext"))
pytestmark = pytest.mark.skipif(not TOOLS, reason="pdflatex and poppler make and read the report")

DOCUMENT = """[source]
config = "P/study"
configuration = "{label}"
errand = "validation"
assignment = "P"
heimdall = "0123456789abcdef"
written = "2026-10-26T10:00:00+00:00"

[axes]
vary = ["pdf"]
plot_points = []
combine = []
fixed = {{}}

[quantities.pdf]
points = [
  {{ tag = "A", value = "A", label = "PDF A" }},
  {{ tag = "B", value = "B", label = "PDF B" }},
]

[plot]
backend = ["mpl"]
draw = ["totality"]

[members.A]
index = 0
choice = {{ pdf = 0 }}
values = {{ pdf = 0 }}
yoda = "points/A/run.yoda"
identity = "one"
complete = true
events = 1000000

[members.B]
index = 1
choice = {{ pdf = 1 }}
values = {{ pdf = 1 }}
yoda = "points/B/run.yoda"
identity = "two"
complete = true
events = 1000000
"""

CELLS, OBJECTS = ("18x275", "27x920"), ("d01-x01-y01", "d02-x01-y01")


def page(path: Path, colour: str, png: bool) -> None:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (320, 240), colour).save(path, "PDF", resolution=72)
    if png:
        Image.new("RGB", (320, 240), colour).save(path.with_suffix(".png"))


def source(results: Path, name: str, png: bool) -> Path:
    """A configuration's result folder: its document, its points, its totality pages (mpl) and their numbers."""
    where = results / "P" / "validation" / name
    (where / "points").mkdir(parents=True)
    (where / "plot.toml").write_text(DOCUMENT.format(label=name.split("_", 1)[1]), encoding="utf-8")
    for point in ("A", "B"):
        (where / "points" / point).mkdir()
        (where / "points" / point / "run.yoda").write_text("# a YODA\n", encoding="utf-8")
    rows = []
    for n, (cell, obj) in enumerate((c, o) for c in CELLS for o in OBJECTS):
        page(where / "plots" / "totality" / "mpl" / cell / f"{obj}.pdf", ("lightblue", "khaki", "salmon", "plum")[n], png)
        for k, (curve, point) in enumerate((("PDF A", "A"), ("PDF B", "B"))):
            off = 0.1 * (k + 1) * (n + 1)
            rows.append({"page": f"{cell}/{obj}", "cell": cell, "object": f"/ZEUS/{obj}", "curve": curve, "point": point,
                         "reference": "ZEUS", "is_reference": False, "bins": 10, "area": 1.0 + off, "area_err": 0.1,
                         "ref_area": 1.0, "cmp_area": 1.0 + off, "abs_area": off, "yield_weighted_abs_dev": off, "yield_ratio": 1.0 + off,
                         "mean_bin_ratio": 1.0 + off, "mean_abs_ratio_dev": off, "chi2": 9.0 * (1 + off), "ndf": 9, "chi2_ndf": 1.0 + off})
    numbers = where / "statistics" / "totality" / "statistics.csv"
    numbers.parent.mkdir(parents=True)
    with open(numbers, "w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=statstable.STATISTIC_COLUMNS)
        out.writeheader()
        out.writerows(rows)
    return where


@pytest.fixture
def trees(tmp_path, monkeypatch):
    for var in ("HEIMDALL_RESULTS", "HEIMDALL_RECORDS", "HEIMDALL_CONFIGS", "HEIMDALL_REPORTS", "HEIMDALL_CACHE"):
        monkeypatch.setenv(var, str(tmp_path / var.removeprefix("HEIMDALL_").lower()))
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    source(tmp_path / "results", "01_pdf", png=True)
    source(tmp_path / "results", "02_more", png=False)                  # its PNGs rendered from its PDFs
    return tmp_path


def recipe(trees, name: str, text: str) -> Path:
    path = trees / "configs" / "P" / f"{name}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def built(name: str, rest: list[str]) -> tuple[report.Plan, list[str]]:
    said: list[str] = []
    plan = report.planned(name, rest)
    report.build(plan, said.append)
    return plan, said


def named(tex: Path) -> list[str]:
    return re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]*)\}", tex.read_text(encoding="utf-8"))


def test_the_default_report_is_a4_and_holds_everything_it_shows(trees, tmp_path):
    numbers = trees / "results" / "P" / "validation" / "01_pdf" / "statistics" / "totality"
    (numbers / "summary.html").write_text("<p>a summary</p>\n", encoding="utf-8")
    plan, said = built("P/validation", [])
    out = trees / "reports" / "P" / "validation"
    assert plan.out == out and (out / "report.pdf").is_file() and (out / "index.html").is_file()
    sizes = re.findall(r"size:\s+([\d.]+) x ([\d.]+)", subprocess.run(["pdfinfo", "-l", "99", str(out / "report.pdf")],
                                                                     capture_output=True, text=True, encoding="utf-8").stdout)
    assert sizes and all((round(float(w)), round(float(h))) == (595, 842) for w, h in sizes)
    files = named(out / "report.tex")
    assert len(files) >= 8 and all(not Path(f).is_absolute() and ".." not in f and (out / f).is_file() for f in files)
    assert (out / "figures" / "02_Pages_totality" / "005_02_more_18x275_d01-x01-y01.png").is_file()    # rendered
    assert not list(out.glob("report.aux")) and "8 figure(s)" in said[0]
    elsewhere = tmp_path / "lifted"
    shutil.copytree(out, elsewhere)
    subprocess.run(["pdflatex", "-interaction=batchmode", "-halt-on-error", "report.tex"], cwd=elsewhere, check=True,
                   capture_output=True)
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "figures/02_Pages_totality/001_01_pdf_18x275_d01-x01-y01.png" in page and "P/validation/02_more" in page
    assert (out / "stats" / "summaries" / "P_validation_01_pdf__totality.html").is_file()
    assert 'href="stats/summaries/P_validation_01_pdf__totality.html"' in page


def test_a_rebuild_makes_nothing_and_a_changed_page_is_copied_again(trees):
    built("P/validation/01_pdf", [])
    _, said = built("P/validation/01_pdf", [])
    assert "0 file(s) copied" in said[0] and said[0].endswith("0 drawn") and "report.pdf unchanged" in said[1]
    page(trees / "results" / "P" / "validation" / "01_pdf" / "plots" / "totality" / "mpl" / "18x275" / "d01-x01-y01.pdf",
         "black", png=True)
    _, said = built("P/validation/01_pdf", [])
    assert "2 file(s) copied" in said[0] and said[0].endswith("0 drawn") and "A4 page(s)" in said[1]


def test_a_statistics_part_holds_the_sections_chosen(trees):
    bars = statstable.bars()
    rows = statstable.read(trees / "results" / "P" / "validation" / "01_pdf" / "statistics" / "totality" / "statistics.csv")
    document, missing = report.chosen(bars.summary_model(rows, "here"), ["standings", "chi2_ndf:ranking", "area:ranking"])
    assert [s.key for s in document.sections] == ["standings", "category-compatibility"] and missing == ["area:ranking"]
    assert [i.key for i in document.sections[1].items] == ["chi2_ndf-ranking"]
    recipe(trees, "numbers", '[report]\nfrom = ["P/validation/01_pdf"]\n\n[[report.section]]\ntitle = "Standings"\n'
                             'stats = ["chi2_ndf:ranking"]\n\n[[report.section]]\ntitle = "Bars"\nbars = ["*d01*"]\n')
    _, said = built("P/numbers.toml", [])
    out = trees / "reports" / "P" / "validation" / "01_pdf"                     # where results/ has its source
    source = trees / "results" / "P" / "validation" / "01_pdf" / "statistics" / "totality" / "statistics.csv"
    standings = out / "stats" / "01_Standings"                                   # typeset; its numbers beside it
    assert sorted(p.name for p in standings.iterdir()) == ["01_01_pdf__totality.csv", "01_01_pdf__totality.html"]
    assert (standings / "01_01_pdf__totality.csv").read_bytes() == source.read_bytes()
    assert not list(out.rglob("stats/**/*.pdf")) and not list(out.rglob("stats/**/*.png"))
    text = subprocess.run(["pdftotext", str(out / "report.pdf"), "-"], capture_output=True, text=True, encoding="utf-8").stdout
    assert "Head to head" not in text and "top five" not in text.lower() and "PDF B" in text and "Notes" in text.title()
    tex = (out / "report.tex").read_text(encoding="utf-8")
    assert r"\includegraphics" not in tex and r"\begin{hdTable}" in tex and r"\begin{hdNotes}" in tex
    bars = out / "stats" / "02_Bars" / "01_01_pdf"
    assert sorted(p.name for p in bars.iterdir()) == ["001_18x275_d01-x01-y01.csv", "002_27x920_d01-x01-y01.csv"]
    rows = list(csv.DictReader(open(bars / "001_18x275_d01-x01-y01.csv", encoding="utf-8")))
    assert [r["curve"] for r in rows] == ["PDF A", "PDF B"] and rows[0]["chi2_ndf"] == "1.1"     # as the source wrote it
    assert "18x275, d01-x01-y01" in tex and "against ZEUS" in tex
    # How the numbers are made: before the results, a paragraph a metric shown, its formula in display when it has one;
    # the parts keep only the notes on reading their own items
    body = tex.split(r"\begin{document}")[1]
    assert body.index(r"\section*{How the numbers are made}") < body.index(r"\section{Standings}")
    assert body.count(r"\hdDefinition{") == 1 and r"\hdDefinition{χ²/ndf}{\chi^2/\mathrm{ndf} = " in body
    assert r"\hdStatSection{The metrics}" in body
    assert r"What each category asks" not in body                                        # no category section is shown here
    assert r"\hdStatSection{How a page is compared}" in body and "How points are scored" not in body
    assert "Scored from 1 (cost 0) to 3 (cost 1)" in body                              # a metric's thresholds, said
    notes = body[body.index(r"\begin{hdNotes}"):body.index(r"\end{hdNotes}")]
    assert "Per point" in notes and "1 is a true curve" not in notes and "Each page as drawn" not in notes
    assert r"\hyperref[hd:method]{How the numbers are made, page~\pageref*{hd:method}}" in body
    assert "1 is a true curve" in " ".join(text.split())                                  # in the PDF, as prose
    html_part = (standings / "01_01_pdf__totality.html").read_text(encoding="utf-8")
    assert "per bin with an error; 1 is a true curve" in html_part                                    # its own page keeps them all
    page = (out / "index.html").read_text(encoding="utf-8")
    assert page.index('<section class="block" id="method"') < page.index('<section class="block" id="s01-001"')


def test_what_no_section_holds_is_removed_and_own_files_are_copied(trees):
    (trees / "configs" / "P" / "extras").mkdir(parents=True)
    page(trees / "configs" / "P" / "extras" / "sketch.pdf", "grey", png=False)
    path = recipe(trees, "mine", '[report]\nfrom = ["P/validation/01_pdf"]\n\n[[report.section]]\ntitle = "Spectra"\npages = ["d01-*"]\n\n'
                                 '[[report.section]]\ntitle = "Mine"\nfiles = ["extras/*.pdf"]\n')
    built("P/mine.toml", [])
    out = trees / "reports" / "P" / "validation" / "01_pdf"
    assert (out / "figures" / "02_Mine" / "001_sketch.pdf").is_file() and (out / "figures" / "02_Mine" / "001_sketch.png").is_file()
    path.write_text(path.read_text(encoding="utf-8").replace('pages = ["d01-*"]', 'pages = ["d02-*"]'), encoding="utf-8")
    built("P/mine.toml", [])
    assert sorted(p.name for p in (out / "figures" / "01_Spectra").glob("*.pdf")) == \
        ["001_01_pdf_18x275_d02-x01-y01.pdf", "002_01_pdf_27x920_d02-x01-y01.pdf"]


def test_a_compare_figures_pages_are_copied_from_its_run(trees):
    run = trees / "results" / "P" / "validation"
    page(run / "compare" / "both" / "mpl" / "18x275" / "d01-x01-y01.pdf", "teal", png=True)
    page(run / "compare" / "both" / "mpl" / "sheets" / "all.pdf", "teal", png=False)
    recipe(trees, "across", '[report]\nfrom = ["P/validation/01_pdf"]\n\n[[report.section]]\ntitle = "Both"\ncompare = ["both"]\n')
    plan, _ = built("P/across.toml", [])
    assert [g.caption for g in plan.sections[0].grids] == ["P/validation · compare both"]
    assert sorted(p.name for p in (plan.out / "figures" / "01_Both").iterdir()) == \
        ["001_18x275_d01-x01-y01.pdf", "001_18x275_d01-x01-y01.png"]


def test_a_report_is_never_built_into_results(trees):
    plan = report.planned("P/validation/01_pdf", [], trees / "results" / "P" / "here")
    with pytest.raises(HeimdallError, match="never built into results"):
        report.build(plan, print)


def test_a_folder_is_built_from_its_report_toml_and_a_runs_report_beside_it(trees):
    where = trees / "results" / "P" / "validation" / "01_pdf"
    (where / "report.toml").write_text('[report]\ntitle = "Only d02"\n\n[[report.section]]\ntitle = "Spectra"\n'
                                       'pages = ["d02-*"]\n', encoding="utf-8")
    plan, _ = built("P/validation/01_pdf", [])
    out = trees / "reports" / "P" / "validation" / "01_pdf"
    assert plan.title == "Only d02" and (out / "report.pdf").is_file()
    assert sorted(p.name for p in (out / "figures" / "01_Spectra").glob("*.pdf")) == \
        ["001_01_pdf_18x275_d02-x01-y01.pdf", "002_01_pdf_27x920_d02-x01-y01.pdf"]
    mine = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    built("P/validation", [])                                       # the run's, in the folder above: nested, apart
    assert (out.parent / "report.pdf").is_file() and (out.parent / "figures" / "02_Pages_totality").is_dir()
    assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == mine


def test_a_tools_section_holds_its_cards_and_tables_and_compiles(trees, tmp_path):
    record = trees / "records" / "P" / "validation" / "01_pdf"
    for k, (point, identity) in enumerate((("A", "one"), ("B", "two"))):
        (record / "points" / point).mkdir(parents=True)
        (record / "points" / point / ".complete").write_text(identity + "\n", encoding="utf-8")
        cards = record / "logs" / point / "cards"
        cards.mkdir(parents=True)
        (cards / "pythia.cmnd").write_text(f"! from base.cmnd, 100% ± 1 → €\nBeams:eCM = 318.\nPDF:pSet = LHAPDF6:PDF_{point}\n"
                                           f"Random:seed = {k + 7}\nTune:pp = 14 ! a comment of {'x' * 160} ≤ ☃\n",
                                           encoding="utf-8")
        (cards / "sherpa.yaml").write_text(f"PROCESSES:\n- 93 93 -> 93 93:\n    Order: {{QCD: {2 + k}}}\nEVENTS: 100\n",
                                           encoding="utf-8")
        (record / "logs" / point / "context.toml").write_text(
            '[tools.pythia]\ntool = "pythia"\ncard = "/x/pythia.cmnd"\n\n[tools.sherpa]\ntool = "sherpa"\ncard = "/x/sherpa.yaml"\n\n'
            '[tools.rivet]\ntool = "rivet"\nanalyses = ["ZEUS_2012_I1116258"]\n', encoding="utf-8")
    recipe(trees, "given", '[report]\nfrom = ["P/validation/01_pdf"]\n\n[[report.section]]\ntitle = "What they were given"\n'
                           'tools = ["*"]\n')
    _, said = built("P/given.toml", [])
    out = trees / "reports" / "P" / "validation" / "01_pdf"
    folder = out / "tools" / "01_What_they_were_given" / "01_01_pdf"
    assert sorted(p.name for p in folder.iterdir()) == ["pythia.baseline.cmnd", "pythia.varied.csv", "sherpa.baseline.yaml",
                                                        "sherpa.varied.csv"]
    assert (folder / "pythia.baseline.cmnd").read_text(encoding="utf-8").startswith("! from base.cmnd, 100% ± 1 → €\nBeams:eCM")
    assert (folder / "pythia.varied.csv").read_text(encoding="utf-8").splitlines() == [
        "point,label,PDF:pSet,Random:seed", "A,PDF A,LHAPDF6:PDF_A,7", "B,PDF B,LHAPDF6:PDF_B,8"]
    assert "3 tool configuration(s)" in said[0] and (out / "report.pdf").is_file()
    tex = (out / "report.tex").read_text(encoding="utf-8")
    assert r"\begin{Verbatim}[commandchars=\\\{\}]" in tex and r"\hdK{Beams:eCM} \hdP{=} \hdN{318.}" in tex     # highlighted
    assert r"\hdK{Order}\hdP{:} \hdLB{}QCD: 3\hdRB{}" in tex and r"\begin{hdTable}" in tex
    assert r"\DeclareUnicodeCharacter{2603}{?}" in tex and r"\DeclareUnicodeCharacter{2264}{\ensuremath{\leq}}" in tex
    text = subprocess.run(["pdftotext", str(out / "report.pdf"), "-"], capture_output=True, text=True, encoding="utf-8").stdout
    assert "LHAPDF6:PDF_A" in text and "ZEUS_2012_I1116258" in text and "Order: {QCD: 3}" in text
    page = (out / "index.html").read_text(encoding="utf-8")
    assert '<div class="text">' in page and "<code>LHAPDF6:PDF_B</code>" in page and "tools/01_What_they_were_given" in page
    lifted = tmp_path / "lifted"
    shutil.copytree(out, lifted)
    subprocess.run(["pdflatex", "-interaction=batchmode", "-halt-on-error", "report.tex"], cwd=lifted, check=True,
                   capture_output=True)
    _, said = built("P/given.toml", [])
    assert "0 file(s) copied or written" in said[0] and "report.pdf unchanged" in said[1]


def test_a_recipes_look_is_its_preamble_and_a_set_has_its_sub_header(trees):
    """[report]'s look keys in report.tex's preamble (the fonts, the body's size, the accent, a grid's
    columns, no contents); a set's sub-header over its first grid, each grid captioned by its cell, a row a picture."""
    recipe(trees, "look", '[report]\nfrom = ["P/validation/01_pdf"]\nfont = "serif"\nsize = 10.5\naccent = "#d62728"\n'
                          'columns = 3\ncontents = false\n\n[[report.section]]\ntitle = "Spectra"\npages = ["*"]\n')
    built("P/look.toml", [])
    out = trees / "reports" / "P" / "validation" / "01_pdf"
    tex = (out / "report.tex").read_text(encoding="utf-8")
    preamble, body = tex.split(r"\begin{document}")
    assert r"\definecolor{hdaccent}{HTML}{D62728}" in preamble and r"\usepackage{tgtermes}" in preamble and "sansmath" not in preamble
    assert r"\@setfontsize\normalsize{10.5}{14.9}" in preamble and r"\hdContents" not in body
    assert body.count(r"\hdSetHead{totality}{P/\allowbreak{}validation/\allowbreak{}01\_\allowbreak{}pdf}") == 1
    assert r"\hdFact{Curves}{pdf: PDF A, PDF B}" in body and r"\hdCaption{18x275}" in body and r"\hdCaption{27x920}" in body
    assert body.count(r"\begin{picture}") == 2 and r"{\hdPanel d01-x01-y01}" in body           # 3 columns: a row a cell
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "Spectra: totality · 18x275" in page and "Curves: pdf: PDF A, PDF B" in page


SCATTER = """BEGIN YODA_SCATTER2D_V2 /ZEUS/{obj}
Path: /ZEUS/{obj}
Type: Scatter2D
---
# xval	 xerr-	 xerr+	 yval	 yerr-	 yerr+
1.5	0.5	0.5	{a}	1	1
2.5	0.5	0.5	{b}	2	3
END YODA_SCATTER2D_V2
"""


def test_a_figure_has_its_curves_bins_beside_it(trees):
    """a figure whose page document is at hand has a CSV beside it, each curve's bins as its point's YODA
    holds them; made again only when the page document or a YODA changed."""
    pytest.importorskip("yoda")
    where = trees / "results" / "P" / "validation" / "01_pdf"
    for point, (a, b) in (("A", (10, 20)), ("B", (11, 22))):
        (where / "points" / point / "run.yoda").write_text(SCATTER.format(obj="d01-x01-y01", a=a, b=b), encoding="utf-8")
    document = trees / "cache" / "P" / "plots" / "validation" / "01_pdf" / "totality" / "18x275" / "d01-x01-y01.toml"
    document.parent.mkdir(parents=True)
    document.write_text('[page]\nname = "totality/18x275/d01-x01-y01"\n\n'
                        '[[curve]]\nfile = "x.root"\nobject = "A/ZEUS/d01-x01-y01"\nlabel = "PDF A"\n\n'
                        '[[curve]]\nfile = "x.root"\nobject = "B/ZEUS/d01-x01-y01"\nlabel = "PDF B"\n', encoding="utf-8")
    _, said = built("P/validation/01_pdf", [])
    out = trees / "reports" / "P" / "validation" / "01_pdf" / "figures" / "02_Pages_totality"
    rows = list(csv.reader(open(out / "001_01_pdf_18x275_d01-x01-y01.csv", encoding="utf-8")))
    assert rows == [list(report.FIGURE_COLUMNS), ["A", "PDF A", "1", "2", "10", "1", "1"], ["A", "PDF A", "2", "3", "20", "2", "3"],
                    ["B", "PDF B", "1", "2", "11", "1", "1"], ["B", "PDF B", "2", "3", "22", "2", "3"]]
    assert said[0].startswith("report: 4 figure(s) (1 with their data, a CSV each), ")
    assert not (out / "002_01_pdf_18x275_d02-x01-y01.csv").exists()               # no page document: no data
    _, said = built("P/validation/01_pdf", [])
    assert said[0].endswith("0 drawn")
