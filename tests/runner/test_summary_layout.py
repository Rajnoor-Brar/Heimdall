"""Statistics on A4 (V196, V197): every summary page and page image is A4 portrait; a table wider than the
page is cut into column blocks stacked on its page; a page holds whole rows, a band never last; small tables share
a page within their section; the footer counts the pages; the facts, contents and notes come first, each page's
footnote a line of note numbers. The worst case is shaped like a real one (76 points in 38 page cells, 12
objects, 57-character labels), made here."""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from runner import plugins  # noqa: E402
from stats import ranking  # noqa: E402

FIGURES = Path(__file__).resolve().parents[2] / "framework" / "plot" / "figures"
bars = plugins.load(FIGURES / "bars.py", "bars")
paper = bars.paper
PDFS = ("NNPDF23lo", "NNPDF23nlo", "MSTW08lo", "PDF4LHC21", "MSHT20lo_as130", "MSHT20qed_lo",
        "NNPDF40nnlo_hessian_pdfas", "MSTW08lo90cl", "MSHT20nlo_as120", "MSHT20nlo_as118", "NNPDF40MClo_as01180qed",
        "NNPDF40MCnlo_as01180qed", "NNPDF40MClo_as01180", "NNPDF40lopch_as01180", "NNPDF40lo_as01180",
        "HERAPDF20loEig", "HERAPDF20nloEig", "HERAPDF20nloVar", "HERAPDF20JetsNLOEig")


def summary(rows: list[dict], heading: str = "", st=None, values: dict | None = None):
    """The summary of `rows`, ranked as `st` says with the points' `values`, as statstable ranks a set before drawing it."""
    return bars.summary_model(rows, heading, ranking.rank(bars._rows_of(rows), st, None, values))


def worst_rows() -> list[dict]:
    """76 points: 38 page cells (a PDF, the lepton PDF on or off) of two curves (the QED shower), 12 objects. The columns of the
    later defaults draw from their own stream, so the first ones keep their numbers."""
    draw, later = random.Random(7), random.Random(11)
    rows = []
    for pdf in PDFS:
        for lepton in ("lpdfon", "lpdfoff"):
            cell = f"{pdf}_{lepton}"
            for k in range(1, 13):
                obj = f"/ZEUS_2012_I1116258/d{k:02d}-x01-y01"
                for shower in ("on", "off"):
                    area = draw.uniform(0.5, 2.0)
                    rows.append({"page": f"{cell}/d{k:02d}", "cell": cell, "object": obj,
                                 "curve": f"lepton QED shower {shower}", "point": f"{cell}_{shower}",
                                 "reference": "ZEUS 2012", "is_reference": False, "bins": 10, "area": area,
                                 "area_err": 0.01, "ref_area": 1.0, "cmp_area": area, "abs_area": draw.uniform(0.05, 0.4),
                                 "yield_weighted_abs_dev": draw.uniform(0.05, 0.4), "yield_ratio": area,
                                 "mean_bin_ratio": draw.uniform(0.4, 1.6), "mean_abs_ratio_dev": draw.uniform(0.1, 0.9),
                                 "chi2": 0.0, "ndf": 10, "chi2_ndf": draw.uniform(1.0, 60.0),
                                 "log_yield_ratio": draw.uniform(0.0, 0.5), "log_dev_shrunk": draw.uniform(0.0, 0.4),
                                 "tilt": draw.uniform(0.0, 0.5), "peak_pull2": draw.uniform(1.0, 80.0),
                                 "chi2_sigma": later.uniform(-1.0, 15.0), "poisson_dev": later.uniform(1.0, 20.0),
                                 "log_dev_l4": later.uniform(0.0, 0.8), "pull_autocorr": later.uniform(0.0, 1.0),
                                 "log_ratio_roughness": later.uniform(0.0, 0.8), "n_eff": later.uniform(50.0, 1e5)})
    return rows


#: Every metric the fixture has a column for: the defaults, chi2_ndf and the old columns.
LEGACY = ("yield_weighted_abs_dev", "yield_ratio", "mean_bin_ratio", "mean_abs_ratio_dev")
ALL = ranking.settings_of({"metrics": ["chi2_ndf", "log_yield_ratio", "log_dev_shrunk", "tilt", "peak_pull2", *LEGACY], "veto_loss": 10.0,
                         "head_to_head": "NNPDF23lo_lpdfon/d01-x01-y01"})


@pytest.fixture(scope="module")
def worst():
    document = summary(worst_rows(), "eic/zeus_validation/01_pythia_qed_lepton · totality", ALL)
    return document, paper.pages(document)


def texts_inside(figure) -> list[str]:
    """The texts drawn outside the page's margins (none, when all is well)."""
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    w, h = (v * figure.dpi for v in paper.A4)
    side, edge, slack = paper.SIDE * figure.dpi, paper.EDGE * figure.dpi, 1.0
    out = []
    for text in figure.texts:
        box = text.get_window_extent(renderer)
        if box.x0 < side - slack or box.x1 > w - side + slack or box.y0 < edge - slack or box.y1 > h - edge + slack:
            out.append(text.get_text())
    return out


def test_every_page_is_a4_and_drawn_within_its_margins(worst):
    document, pages = worst
    assert len(pages) < 70                                       # the content-sized pages of today were 70
    sections = {p.section.key for p in pages}
    for key in sorted(sections):                                 # each section's first page, and the last page
        page = next(p for p in pages if p.section.key == key)
        figure = paper.figure(document, page, plt)
        try:
            assert tuple(round(v, 2) for v in figure.get_size_inches()) == paper.A4
            assert texts_inside(figure) == [], key
        finally:
            plt.close(figure)


def test_the_footer_counts_the_pages(worst):
    document, pages = worst
    figure = paper.figure(document, pages[-1], plt)
    try:
        assert f"page {len(pages)} of {len(pages)}" in [t.get_text() for t in figure.texts]
    finally:
        plt.close(figure)


def wide_table(rows: int = 30, bands: int = 0) -> object:
    """16 columns of wide numbers, the last four a tail; labels as long as real ones; a band every `bands` rows."""
    out = []
    for i in range(rows):
        if bands and i % bands == 0:
            out.append(paper.Row(f"NNPDF40nnlo_hessian_pdfas_lpdfoff {i // bands}", band=True))
        out.append(paper.Row(f"{i + 1}. NNPDF40nnlo_hessian_pdfas_lpdfoff · lepton QED shower off",
                             [paper.Cell(f"{0.0001 * (i + 1) + 0.05:.4f}") for _ in range(16)]))
    return paper.Table("wide", "A wide table", [f"d{j:02d}" for j in range(1, 13)] + ["total", "wins", "win rate",
                                                                                      "rms rank"], out, tail=4)


def test_a_wide_table_is_cut_into_blocks_stacked_on_its_page():
    table = wide_table()
    shape = paper._table_shape(table)
    assert len(shape.blocks) >= 2
    assert [j for block in shape.blocks for j in block] == list(range(16))              # in order, each once
    assert shape.blocks[-1][-4:] == [12, 13, 14, 15]                                     # the tail on the last
    body = [len([j for j in block if j < 12]) for block in shape.blocks]
    assert max(body) - min(body) <= 1                                                     # split evenly
    assert all(shape.label_width + sum(shape.widths[j] for j in block) <= paper.WIDTH + 1e-9 for block in shape.blocks)
    document = paper.Document("heading", [paper.Section("s", "S", [table])])
    pages = paper.pages(document)
    figure = paper.figure(document, pages[0], plt)
    try:
        drawn = [t.get_text() for t in figure.texts]
        first = pages[0].pieces[0].rows[0]
        label = shape.labels[first][0]
        assert drawn.count(label) == len(shape.blocks)                                     # each block its labels
        assert texts_inside(figure) == []
    finally:
        plt.close(figure)


def test_a_page_holds_whole_rows_and_a_band_never_ends_it():
    table = wide_table(rows=120, bands=5)
    document = paper.Document("heading", [paper.Section("s", "S", [table])])
    pages = paper.pages(document)
    assert len(pages) > 1
    seen = []
    for page in pages:
        (piece,) = page.pieces
        rows = piece.rows
        assert not table.rows[rows[-1]].band                                              # never last
        if len(rows) > 1 and rows[1] != rows[0] + 1:                                      # a group continued
            assert table.rows[rows[0]].band and not table.rows[rows[1]].band
            rows = rows[1:]
        seen += rows
        assert piece.first == (page is pages[0])
    assert seen == list(range(len(table.rows)))                                           # every row once, in order


def test_small_tables_share_a_page_and_each_section_starts_one(worst):
    _, pages = worst
    head_to_head = [p for p in pages if p.section.key == "head-to-head"]
    assert sum(len(p.pieces) for p in head_to_head) == 1                         # the one page `head_to_head` names
    keys = [p.section.key for p in pages]
    for page in pages:                                           # a section's pieces never share a page with another's
        assert {piece.item.key for piece in page.pieces} <= {i.key for i in page.section.items}
    order = ["front"] + [s.key for s in worst[0].sections]
    assert keys == sorted(keys, key=order.index)


def test_a_ranking_continues_on_the_next_page():
    names = [f"point {i}  (12)" for i in range(130)]
    shown = paper.Ranking("r", "A ranking", names, [i / 10 for i in range(130)])
    document = paper.Document("heading", [paper.Section("s", "S", [shown])])
    pages = paper.pages(document)
    assert len(pages) >= 2
    assert [i for p in pages for i in p.pieces[0].rows] == list(range(130))
    assert [p.pieces[0].first for p in pages] == [True] + [False] * (len(pages) - 1)


def test_a_label_wraps_when_that_saves_height():
    shape = paper._table_shape(wide_table())
    assert max(len(lines) for lines in shape.labels) >= 1
    one_line = max(paper.width(r.label) for r in wide_table().rows) + 2 * paper.PAD
    assert shape.label_width <= one_line                         # wrapped only when the table takes less height


def test_a_page_image_is_a4_in_the_grid_that_suits_its_curves(scratch):
    assert bars.grid(19, 2.7)[:2] == (2, 3)                     # long labels: two panels across
    assert bars.grid(4, 1.0)[:2] == (3, 2)                      # short ones: three across, bars taller
    columns, rows, bar, per = bars.grid(400, 1.0)
    assert per < 400 and bar >= bars.LEAST_BAR                  # too many for a page: they continue
    rows_ = [r for r in worst_rows() if r["page"] == "NNPDF23lo_lpdfon/d01"]
    made = bars.page(rows_, scratch / "bars" / "d01", ["pdf", "png"], "NNPDF23lo_lpdfon/d01")
    pdf = (scratch / "bars" / "d01.pdf").read_bytes()
    assert {tuple(map(float, b)) for b in re.findall(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", pdf)} == {
        (595.44, 841.68)}
    many = [dict(rows_[0], point=f"p{i}", curve=f"curve {i}") for i in range(200)]
    made = bars.page(many, scratch / "bars" / "many", ["pdf", "png"], "many")
    pngs = sorted(p.name for p in made if p.suffix == ".png")
    assert len(pngs) >= 2 and pngs[0] == "many_01.png"
    assert len(re.findall(rb"/Type\s*/Page\b(?!s)", (scratch / "bars" / "many.pdf").read_bytes())) == len(pngs)


def test_the_front_matter_holds_the_facts_the_contents_and_every_note_once(worst):
    document, pages = worst
    front = [p for p in pages if p.section.key == "front"]
    assert pages[0] in front and document.facts[0].startswith("76 point(s) in 38 page cell(s), on 12 object(s)")
    starts = {}
    for page in pages:
        for piece in page.pieces:
            starts.setdefault(piece.item.key, page.number)
    contents = next(i for i in front[0].section.items if i.key == "front-contents")
    for (_, _, number, _), target in zip(contents.lines, contents._targets):
        assert number == str(starts[target])                     # each entry, the page it starts on
    assert [s.title for s in document.sections] == [line[1] for line in contents.lines if line[3]]
    numbers = paper.note_numbers(document)
    assert sorted(numbers.values()) == list(range(1, len(numbers) + 1)) and set(numbers) <= set(document.notes)
    named = [k for s in document.sections for i in s.items for k in i.notes]
    assert list(numbers) == list(dict.fromkeys(k for k in named if k in document.notes))   # in the order first named
    notes = next(i for i in front[-1].section.items if i.key == "front-notes")
    assert [n for n, *_ in notes.lines if n] == [f"{n}." for n in range(1, len(numbers) + 1)]   # each once


def test_each_page_footnote_is_a_line_of_note_numbers(worst):
    document, pages = worst
    front = sum(1 for p in pages if p.section.key == "front")
    where = "(page 1)" if front == 1 else f"(pages 1–{front})"
    for page in pages:
        text = paper.footnote(document, page.notes)
        if page.section.key == "front":
            assert text == ""
            continue
        assert re.fullmatch(r"Notes? [\d, ]+ " + re.escape(where) + r": what these numbers are and how they are computed\.",
                            text), text
        assert len(paper.wrap(text, paper.WIDTH, paper.SMALL)) == 1


def test_rows_in_curve_order_are_grouped_under_their_cells():
    document = summary(worst_rows(), "", ALL)
    items = {i.key: i for s in document.sections for i in s.items}
    table = items["chi2_ndf"]
    bands = [r.label for r in table.rows if r.band]
    assert len(bands) == 38 and bands[0] == "NNPDF23lo_lpdfon"
    assert {r.label for r in table.rows if not r.band} == {"lepton QED shower on", "lepton QED shower off"}
    standings = items["leaderboard"]                     # the cells share their objects and reference: one order, no band
    labels = [r.label for r in standings.rows if not r.band]
    assert not any(r.band for r in standings.rows) and labels[0].startswith("1. ") and " · lepton QED shower" in labels[0]
    apart = [dict(r, object=r["object"] + "_" + r["cell"]) for r in worst_rows()]          # each cell its own objects
    banded = next(i for s in summary(apart, "", ALL).sections for i in s.items if i.key == "leaderboard")
    assert len([r for r in banded.rows if r.band]) == 38 and any(r.label.startswith("1. lepton QED shower") for r in banded.rows)
    assert standings.headers[:3] == ["loss", "worst page", "worst"] and "veto" in standings.headers
    assert all(c.cells[1].align == "left" for c in standings.rows if not c.band)    # the worst page's name
    one = summary([dict(r, cell="") for r in worst_rows() if r["cell"] == "NNPDF23lo_lpdfon"], "", ALL)
    assert not any(r.band for s in one.sections for i in s.items if isinstance(i, paper.Table) for r in i.rows)


# ── page cells against curves (V198) ─────────────────────────────────────────────────────────────────

def test_cells_against_curves_hold_each_points_mean_the_longer_list_down():
    import math
    rows = worst_rows()
    document = summary(rows, "", ALL)
    items = {i.key: i for s in document.sections for i in s.items}
    keys = [i.key for s in document.sections if s.key == "category-normalisation" for i in s.items
            if i.key.startswith("yield_ratio")]
    assert keys == ["yield_ratio-ranking", "yield_ratio-crossed", "yield_ratio"]
    crossed = items["chi2_ndf-crossed"]
    assert crossed.headers == ["lepton QED shower on", "lepton QED shower off", "rms"]   # 38 cells down, 2 across
    assert [r.label for r in crossed.rows][:2] == ["NNPDF23lo_lpdfon", "NNPDF23lo_lpdfoff"]
    assert crossed.rows[-1].label == "rms" and crossed.rows[-1].bold and len(crossed.rows) == 39
    means = bars._means(rows, "chi2_ndf")
    first = crossed.rows[0]
    on, off = means["NNPDF23lo_lpdfon_on"][0], means["NNPDF23lo_lpdfon_off"][0]
    assert [c.text for c in first.cells] == [bars._shown(on), bars._shown(off), bars._shown(math.sqrt((on * on + off * off) / 2))]
    assert [c.bold for c in first.cells[:2]] == [on <= off, off <= on]          # the best in its row
    ratio = items["yield_ratio-crossed"].rows[0].cells
    a, b = (means_ := bars._means(rows, "yield_ratio"))["NNPDF23lo_lpdfon_on"][0], means_["NNPDF23lo_lpdfon_off"][0]
    assert ratio[2].text == bars._shown(math.sqrt((a * a + b * b) / 2))        # a ratio's too


def test_cells_against_curves_turn_and_leave_gaps_and_are_left_out_when_nothing_crosses():
    rows = [r for r in worst_rows() if r["cell"] in ("NNPDF23lo_lpdfon", "MSTW08lo_lpdfon")]
    many = [dict(r, curve=f"curve {k}", point=f"{r['cell']}_{k}") for r in rows for k in range(5)]
    many = [r for r in many if not (r["cell"] == "MSTW08lo_lpdfon" and r["curve"] == "curve 4")]
    crossed = next(i for s in summary(many, "", ALL).sections for i in s.items if i.key == "chi2_ndf-crossed")
    assert crossed.headers == ["NNPDF23lo_lpdfon", "MSTW08lo_lpdfon", "rms"]  # 5 curves down, 2 cells across
    assert [r.label for r in crossed.rows] == [f"curve {k}" for k in range(5)] + ["rms"]
    assert crossed.rows[4].cells[1].text == "–" and crossed.rows[4].cells[0].text != "–"   # no such point
    one_cell = [r for r in worst_rows() if r["cell"] == "NNPDF23lo_lpdfon"]
    alone = [dict(r, curve=f"{r['cell']} {r['curve']}") for r in worst_rows()[:96]]     # no curve in two cells
    for case in (one_cell, alone):
        assert not any(i.key.endswith("-crossed") for s in summary(case, "", ALL).sections for i in s.items)


# ── summary.html (V199) ──────────────────────────────────────────────────────────────────────────────

def page_of(document) -> tuple[str, dict]:
    """The document's HTML, and what is in it: ids, local links, other references, each item's <tbody> count."""
    from html.parser import HTMLParser
    text = bars.webpage.render(document, paper.note_numbers(document), paper)
    found = {"ids": set(), "links": [], "others": [], "bodies": {}, "pins": set()}

    class Reader(HTMLParser):
        item = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if "id" in attrs:
                found["ids"].add(attrs["id"])
                if tag == "figure":
                    Reader.item = attrs["id"]
            for name in ("href", "src"):
                if name in attrs:
                    (found["links"] if attrs[name].startswith("#") else found["others"]).append(attrs[name])
            if tag == "tbody":
                found["bodies"][Reader.item] = found["bodies"].get(Reader.item, 0) + 1
            if tag == "tr" and "pin" in (attrs.get("class") or ""):
                found["pins"].add(Reader.item)
    Reader().feed(text)
    return text, found


def test_the_page_holds_every_section_and_item_its_links_resolve_and_it_needs_nothing_else(worst):
    document, _ = worst
    text, found = page_of(document)
    assert text.startswith("<!DOCTYPE html>") and '<meta charset="utf-8">' in text
    for section in document.sections:
        assert bars.webpage.anchor("s", section.key) in found["ids"]
        assert all(bars.webpage.anchor("i", i.key) in found["ids"] for i in section.items)
    assert found["links"] and all(link[1:] in found["ids"] for link in found["links"])    # every link lands
    assert found["others"] == [] and "http" not in text and "<script src" not in text      # self-contained
    numbers = paper.note_numbers(document)
    assert {f"note-{n}" for n in numbers.values()} <= found["ids"]
    assert found["bodies"]["i-chi2_ndf"] == 38                                   # a <tbody> a cell's band
    assert found["pins"] == {f"i-{k}-crossed" for k in ALL.metrics}              # the mean row stays last


def test_the_page_escapes_its_text_and_reads_mathtext():
    table = paper.Table("t", "A <b> & title", ["$\\chi^{2}$/ndf", "x_{1}"],
                        [paper.Row("<script>alert(1)</script> & co", [paper.Cell("1.5"), paper.Cell("<2")])])
    text, _ = page_of(paper.Document("a & b", [paper.Section("s", "S", [table])], {"n": "x < y"}, ["4 < 5"]))
    assert "<script>alert" not in text and "&lt;script&gt;alert(1)&lt;/script&gt; &amp; co" in text
    assert "A &lt;b&gt; &amp; title" in text and "&lt;2" in text and "4 &lt; 5" in text
    assert bars.webpage.text_of("$\\chi^{2}$/ndf") == "χ<sup>2</sup>/ndf"
    assert bars.webpage.text_of("$p_{T}$ [GeV]") == "p<sub>T</sub> [GeV]"
    assert bars.webpage.text_of("costs $5") == "costs $5"                      # a lone dollar is a dollar


def test_the_summary_writes_its_page_whatever_the_formats(scratch):
    rows = [r for r in worst_rows() if r["cell"] in ("NNPDF23lo_lpdfon", "NNPDF23lo_lpdfoff")]
    made = bars.summary_of(rows, scratch / "html" / "summary", ["png"], "a · b", ranking.rank(rows, ALL))
    assert scratch / "html" / "summary.html" in made and not (scratch / "html" / "summary.pdf").exists()
    assert "<title>Statistics: a · b</title>" in (scratch / "html" / "summary.html").read_text(encoding="utf-8")


def test_the_sets_index_links_each_sets_statistics(scratch):
    from runner import plot
    run = scratch / "indexed"
    for folder in ("plots/totality/mpl", "plots/pdfs/mpl", "statistics/totality"):
        (run / folder).mkdir(parents=True, exist_ok=True)
    for page in ("plots/totality/mpl/index.html", "plots/pdfs/mpl/index.html", "statistics/totality/summary.html"):
        (run / page).write_text("<html></html>", encoding="utf-8")
    index = plot.write_sets_index(run / "plots", "a run").read_text(encoding="utf-8")
    assert '<a href="../statistics/totality/summary.html">statistics</a>' in index
    assert "../statistics/pdfs/" not in index                                   # no summary there: no link


def test_a_bar_far_beyond_the_rest_is_cut_and_every_value_stays_on_its_panel(scratch):
    """V205: a curve gone wild (Sherpa with one PDF: σ 10⁹ times the rest, a mean ratio of −3.8·10⁸) put its value
    10⁸ pixels off the panel, more than FreeType could raster; a negative value drew over the curve labels."""
    assert paper.reach([0.3, 0.8, 0.5, 0.2, 3.8e8]) == 0.8 and paper.reach([1.0, 30.0]) == 30.0
    assert paper.reach([0.0, 0.0, 5.0]) == 5.0 and paper.reach([]) == 0.0
    wild = {"area": 1.3e13, "yield_ratio": 7.2e9, "mean_bin_ratio": -3.8e8, "yield_weighted_abs_dev": 8.0e9, "mean_abs_ratio_dev": 4.3e9,
            "chi2_ndf": 1.86}
    rows = [r for r in worst_rows() if r["page"] == "NNPDF23lo_lpdfon/d01"]
    rows = [dict(rows[0], point=f"p{i}", curve=f"curve {i}", mean_bin_ratio=0.5 - 0.15 * i) for i in range(6)] + \
        [dict(rows[0], point="wild", curve="wild", **wild)]
    label = max(paper.width(r["curve"], 8) for r in rows) + 0.12
    shown = bars.panels(["chi2_ndf", "yield_weighted_abs_dev", "yield_ratio", "mean_bin_ratio", "mean_abs_ratio_dev"])
    columns, _, bar, _ = bars.grid(len(rows), label, len(shown))
    figure = bars._page_figure(rows, "a page", columns, bar, label, plt, shown)
    figure.savefig(scratch / "wild.png", dpi=150)                          # raster overflow before
    renderer = figure.canvas.get_renderer()
    for ax in figure.axes:
        panel = ax.get_window_extent(renderer)
        for text in ax.texts:
            box = text.get_window_extent(renderer)
            assert panel.x0 - 1 <= box.x0 and box.x1 <= panel.x1 + 1, (ax.get_title(loc="left"), text.get_text())
    said = {ax.get_title(loc="left"): [t.get_text() for t in ax.texts] for ax in figure.axes}
    assert said["mean bin ratio"][-1] == "-3.8e+08 «" and said["yield ratio"][-1] == "» 7.2e+09"
    assert paper.CUT_KEY in [t.get_text().replace("\n", " ") for t in figure.texts]          # its key at the foot
    plt.close(figure)
    shown = paper.Ranking("r", "mean ratio", [f"p{i}" for i in range(7)], [0.9, 1.1, 0.8, 1.2, 0.95, 1.05, -3.8e8],
                            base=1.0)
    document = paper.Document("heading", [paper.Section("s", "S", [shown])])
    figure = paper.figure(document, paper.pages(document)[0], plt)
    assert "-3.8e+08 «" in [t.get_text() for t in figure.texts] and not texts_inside(figure)
    plt.close(figure)
    page = bars.webpage.render(document, paper.note_numbers(document), paper)
    assert "-3.8e+08 «" in page and f"background:{paper.WILD[1]}" in page


def test_a_bar_is_blue_or_orange_by_its_side_violet_or_golden_when_cut_pink_or_red_when_absurd(scratch):
    """The user, 2026-10-26: "blue, indigo/violet, pink for positive; orange, golden yellow, red for negative"."""
    values = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 0.95, -0.5, 40.0, -40.0, 2e7, -2e7, float("inf")]
    figure = plt.figure()
    ax = figure.add_subplot()
    assert bars._bars(ax, values, [""] * len(values), panel=2.5)
    colours = [paper.colour_of(v, paper.reach(values), paper.absurd_from(values)) for v in values]
    assert colours == [paper.ABOVE] * 10 + [paper.BELOW, paper.TOO_BIG[0], paper.TOO_BIG[1], paper.WILD[0],
                                            paper.WILD[1], paper.WILD[0]]
    import matplotlib.colors as mc
    assert [mc.to_hex(bar.get_facecolor()) for bar in ax.patches] == [mc.to_hex(c) for c in colours]
    assert [t.get_text() for t in ax.texts][-6:] == ["-0.5", "» 40", "-40 «", "» 2e+07", "-2e+07 «", "» ∞"]
    plt.close(figure)
    figure = plt.figure()
    assert not bars._bars(figure.add_subplot(), [0.5, 1.0, -0.2], ["", "", ""])          # nothing cut: no key
    plt.close(figure)


# ── scored by category (stats-backend phase 6) ───────────────────────────────────────────────────────

def keys_of(document):
    return {s.key: [i.key for i in s.items] for s in document.sections}


def test_the_default_summary_is_the_leaderboard_then_a_section_per_category_with_a_metric_on():
    document = summary(worst_rows(), "", ranking.settings_of())
    keys = keys_of(document)
    assert list(keys) == ["leaderboard", "category-compatibility", "category-normalisation", "category-accuracy", "category-trend",
                          "category-defects"]                                  # the nine defaults; no similarity, no quality
    assert keys["leaderboard"] == ["leaderboard", "categories"]
    pairs = {"compatibility": ("chi2_sigma", "poisson_dev"), "accuracy": ("log_dev_shrunk", "log_dev_l4"),
             "trend": ("tilt", "pull_autocorr"), "defects": ("peak_pull2", "log_ratio_roughness")}    # 02's pairs
    for category, (a, b) in pairs.items():
        assert keys[f"category-{category}"] == [f"category-{category}-ranking", f"{a}-ranking", f"{a}-crossed", a,
                                                f"{b}-ranking", f"{b}-crossed", b]
    assert keys["category-normalisation"][1:] == ["log_yield_ratio-ranking", "log_yield_ratio-crossed", "log_yield_ratio"]
    standings = next(i for s in document.sections for i in s.items if i.key == "leaderboard")
    assert "veto" not in standings.headers and "dominated" not in standings.headers
    assert not any(s.key == "head-to-head" for s in document.sections)         # only when asked


def test_the_leaderboard_is_the_engines_losses_and_veto_and_dominated_columns_follow_the_settings():
    st = ranking.settings_of({"veto_loss": 0.5, "dominated": True})
    rows = worst_rows()
    document = summary(rows, "", st)
    standings = next(i for s in document.sections for i in s.items if i.key == "leaderboard")
    assert standings.headers[:4] == ["loss", "worst page", "worst", "veto"] and standings.headers[-1] == "dominated"
    scored = {p.point: p for p in ranking.rank(rows, st).points}
    first = next(r for r in standings.rows if not r.band)
    best = ranking.rank(rows, st).points[0]                                       # the engine's first, vetoed or not
    assert first.cells[0].text == bars._shown(best.loss)
    assert first.cells[1].text == best.worst_page.rsplit("/", 1)[-1]
    assert (first.cells[3].text == "veto") == best.vetoed


def test_a_purposes_section_says_what_it_asks_and_each_metric_what_it_is_and_how_it_is_scored():
    from stats import metrics
    document = summary(worst_rows(), "", ranking.settings_of({"thresholds": {"log_yield_ratio": [0.1, 0.5]}}))
    assert document.notes["category-accuracy"].startswith("Shape accuracy, bin by bin. ")
    assert document.notes["stat-chi2_sigma"] == metrics.describe("chi2_sigma")
    assert "Scored from 0.1 (cost 0) to 0.5 (cost 1)" in document.notes["stat-log_yield_ratio"]    # the setting's thresholds, not the registry's
    ranked = next(i for s in document.sections for i in s.items if i.key == "category-accuracy-ranking")
    assert {"category-accuracy", "loss"} <= set(ranked.notes)


def test_a_head_to_head_is_played_for_the_pages_asked_and_counts_no_wins():
    rows = worst_rows()
    one = summary(rows, "", ranking.settings_of({"head_to_head": "NNPDF23lo_lpdfon/d01-x01-y01"}))
    section = next(s for s in one.sections if s.key == "head-to-head")
    (table,) = section.items
    assert table.headers == ["lepton QED shower on", "lepton QED shower off", "loss"]
    on, off = table.rows[0].cells, table.rows[1].cells
    assert on[0].text == "–" and off[1].text == "–"
    assert float(on[1].text) == pytest.approx(-float(off[0].text))              # the pair, seen from each side
    every = summary(rows, "", ranking.settings_of({"head_to_head": "all"}))
    assert len(next(s for s in every.sections if s.key == "head-to-head").items) == 12 * 38
    none = summary(rows, "", ranking.settings_of({"head_to_head": "nowhere/d99"}))
    assert not any(s.key == "head-to-head" for s in none.sections)


def test_a_table_past_bad_still_tells_its_worst_from_its_next():
    document = summary(worst_rows(), "", ranking.settings_of({"metrics": ["chi2_ndf"]}))
    table = next(i for s in document.sections for i in s.items if i.key == "chi2_ndf")
    fills = {tuple(c.fill) for r in table.rows if not r.band for c in r.cells[:-1]}
    assert len(fills) > 5                                                        # not one dark block


def test_a_page_image_has_a_panel_a_metric_on(scratch):
    rows = [r for r in worst_rows() if r["page"] == "NNPDF23lo_lpdfon/d01"]
    made = bars.page(rows, scratch / "bars" / "d01", ["png"], "d01", ["chi2_ndf", "log_yield_ratio", "peak_pull2"])
    assert [p.name for p in made] == ["d01.png"]
    assert bars.grid(4, 1.0, 3)[:2] == (3, 1)                                    # three panels fit across
    assert [t for _, t in bars.panels(["chi2_ndf", "tilt"])] == ["χ²/ndf", "tilt, Δ ln ratio across the page"]
    assert [n for n, _ in bars.panels()] == ["chi2_sigma", "poisson_dev", "log_yield_ratio", "log_dev_shrunk", "log_dev_l4", "tilt",
                                             "pull_autocorr", "peak_pull2", "log_ratio_roughness"]


def test_a_metric_off_or_without_numbers_has_no_section():
    rows = [{k: v for k, v in r.items() if k not in ("tilt", "pull_autocorr")} for r in worst_rows()]
    document = summary(rows, "", ranking.settings_of())
    assert "category-trend" not in keys_of(document)
    assert summary([], "", ranking.settings_of()).sections == []


def test_a_curve_with_an_infinite_number_is_drawn_not_a_crash(scratch):
    rows = [r for r in worst_rows() if r["page"] == "NNPDF23lo_lpdfon/d01"]
    rows = [dict(rows[0], chi2_ndf=float("inf")), dict(rows[1])]
    st = ranking.settings_of({"metrics": ["chi2_ndf", "log_yield_ratio"], "head_to_head": "all"})
    made = bars.summary_of(rows, scratch / "inf" / "summary", ["png"], "inf", ranking.rank(rows, st))
    assert made
    document = summary(rows, "", st)
    standings = next(i for s in document.sections for i in s.items if i.key == "leaderboard")
    assert "∞" in [c.text for r in standings.rows for c in r.cells]
    match = next(s for s in document.sections if s.key == "head-to-head").items[0]
    assert match.rows[0].cells[1].text == "+∞" and match.rows[1].cells[0].text == "−∞"
    text, _ = page_of(document)
    assert "background:#nan" not in text.lower() and "nan," not in text.lower().replace("isnan", "")


def worst_axes() -> dict:
    return {f"{pdf}_{lepton}_{shower}": {"pdf": pdf, "lepton": lepton, "shower": shower}
            for pdf in PDFS for lepton in ("lpdfon", "lpdfoff") for shower in ("on", "off")}


def test_marginals_and_a_baseline_are_sections_when_the_points_axes_are_known():
    rows, axes = worst_rows(), worst_axes()
    st = ranking.settings_of({"baseline": {"shower": "on"}})
    document = summary(rows, "", st, axes)
    keys = keys_of(document)
    assert keys["marginals"] == ["marginal-pdf", "marginal-lepton", "marginal-shower"] and keys["baseline"] == ["baseline"]
    assert list(keys)[-2:] == ["marginals", "baseline"]
    pdf = next(i for s in document.sections for i in s.items if i.key == "marginal-pdf")
    assert pdf.headers[:2] == ["× vs strata", "± SE"] and len([r for r in pdf.rows]) == len(PDFS)
    assert {r.cells[pdf.headers.index("n")].text for r in pdf.rows} == {"4"}      # lepton × shower: four strata a PDF
    base = next(i for s in document.sections for i in s.items if i.key == "baseline")
    assert base.headers[:3] == ["loss", "baseline", "Δloss"] and len(base.headers) == 3 + 12
    assert sum(1 for r in base.rows if not r.band and r.label.endswith("(baseline)")) == 38     # the "on" points are their own
    assert "marginals" in document.notes and "baseline" in document.notes
    none = summary(rows, "", st, {})
    assert "marginals" not in keys_of(none) and "baseline" not in keys_of(none)          # no axes known: no sections


def test_a_confounded_marginal_says_so_and_an_unmatched_point_is_listed():
    rows, axes = worst_rows(), worst_axes()
    rows = [r for r in rows if r["point"] != "NNPDF23lo_lpdfon_on"]
    st = ranking.settings_of({"by": ["shower"], "baseline": {"shower": "on"}})
    document = summary(rows, "", st, axes)
    assert keys_of(document)["marginals"] == ["marginal-shower"]
    shower = next(i for s in document.sections for i in s.items if i.key == "marginal-shower")
    unmatched = {r.label: r.cells[shower.headers.index("unmatched")].text for r in shower.rows}
    assert unmatched == {"on": "0", "off": "1"}                                   # NNPDF23lo_lpdfon holds its "off" point alone
    assert document.notes["headline-shower"].startswith("shower: ")
    assert "NNPDF23lo_lpdfon_off" in document.notes["unmatched"] and "no point equal to it" in document.notes["unmatched"]
    with pytest.raises(Exception, match="not a quantity"):
        summary(rows, "", ranking.settings_of({"by": "beams"}), axes)


def test_a_vetoed_point_is_last_in_the_leaderboard_and_its_note_says_why():
    rows = [dict(r, peak_bin_ratio=0.0, yield_sign=0.0) for r in worst_rows()]
    st = ranking.settings_of()
    best = ranking.rank(bars._rows_of(rows), st).points[0].point
    rows = [dict(r, yield_sign=1.0) if r["point"] == best and not r["is_reference"] else r for r in rows]
    document = summary(rows, "", st)
    standings = next(i for s in document.sections for i in s.items if i.key == "leaderboard")
    last = [r for r in standings.rows if not r.band][-1]
    assert last.label.startswith("– ") and last.cells[standings.headers.index("veto")].text == "veto"
    assert "vetoed" in standings.notes and "a yield of zero or less on" in document.notes["vetoed"]
