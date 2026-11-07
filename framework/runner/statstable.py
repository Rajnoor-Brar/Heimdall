"""The statistics table (V160, V164): the rows and the csv are stats/table.py's (re-exported here); this module
keeps what needs the runner: the bar graphs and the summary (rank 4).

plot.py measures (Paint writes each page's <page>.toml.stats.json) and calls these; the report reads a source's
statistics.csv with `read` and lays out its summary's sections itself. A page is plot's `Page`: its config,
document, curves' plain labels, name, cell, object and set.
"""

from __future__ import annotations

from pathlib import Path

from stats.table import (COUNTS, FORMAT, SIDECAR, STATISTIC_COLUMNS, TEXT, columns_for, default_metrics, format_of,  # noqa: F401 (re-exported)
                         read, sidecar, statistics_of, write_statistics)

from . import plugins
from .paths import heimdall_root, results_root


def bars():
    """framework/plot/figures/bars.py, loaded (V162): the bar graphs and the summary."""
    return plugins.load(heimdall_root() / "framework" / "plot" / "figures" / "bars.py", "bars")


def heading_of(numbers: Path) -> str:
    """A set's statistics' heading (V196): its run folder under results/ (else that folder's last two parts) and
    the set, "eic/zeus_validation/01_pythia_qed_lepton · qed_lepton_by_pdf"."""
    run = numbers.parent.parent
    try:
        where = run.resolve().relative_to(results_root().resolve()).as_posix()
    except ValueError:
        where = "/".join(run.parts[-2:])
    return f"{where} · {numbers.name}"


def write_set(pages: list, numbers: Path, formats: list[str], module=None) -> tuple[int, int]:
    """A set's numbers, statistics/<set>/ (V160, V164): statistics.csv, then each page's bar graph and the summary
    (bars.draw), when any page has numbers. (rows written, images made). `module`: bars, loaded once by the caller."""
    count = write_statistics(pages, numbers / "statistics.csv")
    if not count:
        return 0, 0
    module = module or bars()
    images = module.draw([(p.rel, statistics_of(p) or []) for p in pages], numbers / "bars", formats,
                         summary=numbers / "summary", heading=heading_of(numbers))
    return count, images
