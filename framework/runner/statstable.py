"""The statistics table (V160, V164): the rows and the csv are stats/table.py's (re-exported here); this module
keeps what needs the runner: the bar graphs and the summary (rank 4).

plot.py measures (Paint writes each page's <page>.toml.stats.json) and calls these; the report reads a source's
statistics.csv with `read` and lays out its summary's sections itself. A page is plot's `Page`: its config,
document, curves' plain labels, name, cell, object and set.
"""

from __future__ import annotations

from pathlib import Path

from stats.table import (COUNTS, FORMAT, SIDECAR, STATISTIC_COLUMNS, TEXT, columns_for, default_metrics, format_of,  # noqa: F401 (re-exported)
                         read, sidecar, statistics_of, upgraded, write_statistics)

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


def ranking_of(errand, set_: str) -> dict:
    """The [ranking] a set is ranked with: the errand's, a set's own `ranking` laid over it (a plain dict)."""
    from stats import ranking
    from .sweep import set_entries
    sets = (errand.plot or {}).get("sets")
    own = next((s.ranking for s in set_entries(sets, "[plot].sets") if s.name == set_), {}) if sets else {}
    return ranking.overlaid(errand.ranking, own)


def metric_names(errand_stats: dict | None, ranking_table: dict | None) -> list[str]:
    """The metric columns a table carries: `[stats].metrics` (the defaults when it names none) and every metric `[ranking]`
    has on, so that whatever is ranked by is there to read."""
    from stats import ranking
    names = list((errand_stats or {}).get("metrics") or default_metrics())
    return names + [n for n in ranking.settings_of(ranking_table).metrics if n not in names]


def point_values(numbers: Path) -> dict:
    """What each point's sweep chose, {point: {quantity: tag}}, from the run's plot document (statistics/<set> is beside it);
    {} when it has none to read."""
    import tomllib
    path = numbers.parent.parent / "plot.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    quantities = data.get("quantities", {})
    out = {}
    for name, member in (data.get("members") or {}).items():
        chosen = {}
        for quantity, index in (member.get("choice") or {}).items():
            points = (quantities.get(quantity) or {}).get("points") or []
            if isinstance(index, str):                         # by tag (plotdoc.by_tag)
                chosen[quantity] = index
            elif isinstance(index, int) and 0 <= index < len(points) and "tag" in points[index]:
                chosen[quantity] = str(points[index]["tag"])
        if chosen:
            out[name] = chosen
    return out


def write_set(pages: list, numbers: Path, formats: list[str], module=None, names=None, ranking: dict | None = None) -> tuple[int, int]:
    """A set's numbers, statistics/<set>/ (V160, V164): statistics.csv and statistics.json (the metrics `names`, ranked as
    `ranking` says), then each page's bar graph and the summary (bars.draw), when any page has numbers. (rows written,
    images made). `module`: bars, loaded once by the caller."""
    from stats import ranking as engine
    names = list(names) if names is not None else metric_names(None, ranking)
    values = point_values(numbers)
    merged = {name: members for page in pages for name, members in getattr(page, "merged", {}).items()}
    count = write_statistics(pages, numbers / "statistics.csv", names, ranking=ranking, values=values, merged=merged)
    if not count:
        return 0, 0
    module = module or bars()
    images = module.draw([(p.rel, statistics_of(p, names) or []) for p in pages], numbers / "bars", formats,
                         summary=numbers / "summary", heading=heading_of(numbers), st=engine.settings_of(ranking), axes=values)
    return count, images
