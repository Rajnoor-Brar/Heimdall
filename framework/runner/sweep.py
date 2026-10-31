"""Points and pages from `sweeps` and `plot_points` (rank 1).

docs/04_Config_Reference.md §5.1–5.2. A string entry of `sweeps` is an independent axis; a list
entry is an entangled group that moves together (value i with value i); a `Listed` entry is listed
combinations of quantities, a row each, a row setting some of them (V154). The points are the grid of
the axes, in `sweeps` order. Pages are the grid of the `plot_points` axes, and every other swept
quantity becomes the curves on a page.
"""

from __future__ import annotations

import fnmatch
import itertools
import re
from dataclasses import dataclass, field

from . import schema
from .errors import HeimdallError, did_you_mean


@dataclass
class Point:
    index: int                                      # 1-based
    name: str                                       # tags joined by "_", in sweeps order; "point" if none
    choice: dict[str, int] = field(default_factory=dict)   # swept quantity → value index
    page: tuple = ()                                # the plot_points part of the choice
    stage: str = ""                                 # "pre", "post", "combined" (a merged group, V35): not a point


def tag_of(quantity, index: int) -> str:
    if quantity.tags:
        return quantity.tags[index]
    text = re.sub(r"[^A-Za-z0-9.+-]+", "-", str(quantity.values[index])).strip("-")
    return text or f"{quantity.name}{index + 1}"


def label_of(quantity, index: int) -> str:
    return quantity.labels[index] if quantity.labels else tag_of(quantity, index)


class Listed(list):
    """A `vary` entry of listed combinations (V154): the quantities it sets, in the order they first appear in
    its rows (the list itself, so the code that reads a group as its names reads this too), and its rows, each
    {quantity: value index} for the quantities that row sets. A row may leave a quantity out: that point sets
    nothing for it."""
    def __init__(self, members, rows: list[dict[str, int]]):
        super().__init__(members)
        self.rows = rows


def axes(configuration) -> list[list[str]]:
    return [entry if isinstance(entry, list) else [entry] for entry in configuration.sweeps]


def split_axes(configuration) -> tuple[list, list]:
    """(page groups, curve groups): a group with a member in plot_points makes pages, as a whole; a listed group is
    split, the members plot_points names making pages and the others curves (V154)."""
    pages_, curves = [], []
    for group in axes(configuration):
        named = [m for m in group if m in configuration.plot_points]
        if not named:
            curves.append(group)
        elif isinstance(group, Listed):
            pages_.append(Listed(named, group.rows))
            if rest := [m for m in group if m not in named]:
                curves.append(Listed(rest, group.rows))
        else:
            pages_.append(group)
    return pages_, curves


def group_key(group, choice: dict):
    """What tells a group's points apart: its value index (an entangled group moves together), or a listed
    group's members' indices (-1 where a row leaves one out)."""
    if isinstance(group, Listed):
        return tuple(choice.get(m, -1) for m in group)
    return choice[group[0]]


def group_tag(quantities: dict, group, choice: dict) -> str:
    """A group's tag at a point: its first quantity's, or a listed group's present members' joined."""
    if isinstance(group, Listed):
        return "_".join(tag_of(quantities[m], choice[m]) for m in group if m in choice)
    return tag_of(quantities[group[0]], choice[group[0]])


def group_labels(quantities: dict, group, choice: dict) -> list[str]:
    """A group's labels at a point: its first quantity's, or a listed group's present members'."""
    if isinstance(group, Listed):
        return [label_of(quantities[m], choice[m]) for m in group if m in choice]
    return [label_of(quantities[group[0]], choice[group[0]])]


def kept(run, group: list[str]) -> list[int]:
    """The value indices an axis sweeps: all but those its quantities `exclude` (1-based, V42). An
    entangled group moves together, so a value excluded by any of its quantities leaves the group."""
    dropped = {i - 1 for name in group for i in run.quantities[name].exclude}
    indices = [i for i in range(len(run.quantities[group[0]].values)) if i not in dropped]
    if not indices:
        raise HeimdallError(f"exclude leaves the entangled group {group} no value", where=f"{run.path}",
                       hint="its quantities' exclude lists together cover every value")
    return indices


#: Names a point may not have: what lives beside the points in a configuration's folder (U30).
RESERVED = ("plots", "pre", "post", "cluster")


def points(run, configuration) -> list[Point]:
    groups = axes(configuration)
    ranges = [range(len(group.rows)) if isinstance(group, Listed) else kept(run, group) for group in groups]
    page_groups = split_axes(configuration)[0]
    out: list[Point] = []
    for number, combination in enumerate(itertools.product(*ranges), start=1):
        choice: dict[str, int] = {}
        for group, index in zip(groups, combination):
            choice.update(group.rows[index] if isinstance(group, Listed) else {name: index for name in group})
        tags = [tag_of(run.quantities[name], choice[name]) for group in groups for name in group
                if name in choice and not run.quantities[name].silent]   # a compound quantity's later fields (v3)
        page = tuple(group_key(group, choice) for group in page_groups)
        out.append(Point(index=number, name="_".join(tags) or "point", choice=choice, page=page))
    names = [p.name for p in out]
    for name in names:
        if name in RESERVED:
            raise HeimdallError(f"a point is named '{name}', which is where the configuration's "
                           + {"plots": "pages", "pre": "pre stage", "post": "post stage", "cluster": "cluster submissions"}[name]
                           + " live", where=f"{run.path}",
                           hint=f"give that value another tag; {', '.join(RESERVED)} are reserved")
    clashes = sorted({n for n in names if names.count(n) > 1})
    if clashes:
        raise HeimdallError(f"these points would share a directory: {', '.join(clashes)}", where=f"{run.path}",
                       hint="give the swept quantities distinct tags (see C11)")
    return out


def pages(configuration, point_list: list[Point]) -> dict[tuple, list[Point]]:
    """page key → its points, in point order. No plot_points: one page with every point."""
    out: dict[tuple, list[Point]] = {}
    for point in point_list:
        out.setdefault(point.page, []).append(point)
    return out


def select_points(run, configuration, point_list: list[Point], selector: str | None) -> list[Point]:
    """--points: comma-separated tags, 1-based indices, point names or quantity=tag filters. A whole
    point name picks that point alone (heimdall cluster's jobs name theirs, V114), before any tag match."""
    if not selector:
        return point_list
    chosen = []
    for item in [s.strip() for s in selector.split(",") if s.strip()]:
        if "=" in item:
            name, _, wanted = item.partition("=")
            if name not in run.quantities:
                raise HeimdallError(f"--points: '{name}' is not a quantity")
            matched = [p for p in point_list if name in p.choice and tag_of(run.quantities[name], p.choice[name]) == wanted]
        elif item.isdigit():
            matched = [p for p in point_list if p.index == int(item)]
        else:
            matched = [p for p in point_list if p.name == item] or [p for p in point_list if item in p.name.split("_")]
        if not matched:
            raise HeimdallError(f"--points: '{item}' matches no point", hint=", ".join(p.name for p in point_list[:8]))
        chosen += [p for p in matched if p not in chosen]
    return chosen


# ── page sets (V159): pages of chosen points, whatever the plot axes; V163: of axes, as products ─────────

#: Names a set may not have (V164): its folder plots/<set>/ holds these, the backends' (and older layouts had them in plots/).
RESERVED_SETS = ("root", "mpl", "yoda", "statistics")
#: A set table's own keys (V163); the rest are [plot] page keys, for its pages.
SET_KEYS = ("name", "points", "pages", "curves", "reference", "look")
#: The line styles a curve may take (Paint's, src/Apps/Paint/Page.hh), in the order a look's line axis takes them.
CURVE_LINES = ("solid", "dashed", "dotted", "dashdot")


def check_curve_style(look, where: str) -> None:
    """A quantity value's curve look (V67): colour ("#rrggbb", a ROOT name or number), line, width
    (points); "default" for a key is the style's, as if left out."""
    if not isinstance(look, dict):
        raise HeimdallError("a style is a table, { colour, line, width }", where=where)
    for key, value in look.items():
        if value == schema.DEFAULT:
            continue
        if key == "colour":
            ok = isinstance(value, str) and value or isinstance(value, int) and not isinstance(value, bool)
        elif key == "line":
            ok = value in CURVE_LINES
        elif key == "width":
            ok = isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
        else:
            raise HeimdallError(f"a style has no key '{key}'", where=where, hint=did_you_mean(key, ["colour", "line", "width"])
                           or "its keys: colour, line, width")
        if not ok:
            raise HeimdallError(f"style {key} = {value!r} is not one", where=where,
                           hint={"colour": '"#rrggbb", a ROOT colour name ("kBlue+1") or number',
                                 "line": " | ".join(CURVE_LINES), "width": "a number of points > 0"}[key])


@dataclass
class SetSpec:
    """One entry of [plot].sets. V159's: a folder of the points its selectors name, in their order. V163's
    table: `pages`, a filter whose keys are the page axes (a page cell per combination of their values among
    the set's points), and `curves`, a filter or a list of them (the union, in order); a filter is
    {quantity: what}, every combination of its quantities' values (an outer product). `pages = "none"` (or
    [] or {}: V178) is no page axis at all: a page per object, every curve on it."""
    name: str                                   # its folder
    selectors: list = field(default_factory=list)   # V159's points
    pages: dict | None = None                   # quantity → its matcher (the raw value); {}: none; None: unset
    curves: list = field(default_factory=list)  # filters
    reference: dict | None = None               # a filter: the curve moved first on each page
    look: object = None                         # {"colour": q, "line": q}, "palette", or None (automatic)
    keys: dict = field(default_factory=dict)    # the [plot] page keys it sets for its pages
    where: str = ""

    @property
    def axes(self) -> bool:
        """It names its axes (V163): its pages are cells of them, an axis it does not name is paged."""
        return self.pages is not None or bool(self.curves)


def set_page_keys() -> tuple[str, ...]:
    """What a set table may set for its pages (V163): [plot]'s page keys but sets, and objects and style."""
    return tuple(k for k, e in schema.keys("plot").items() if e.get("page") and k != "sets") + ("objects", "style")


def set_entries(sets, where: str) -> list[SetSpec]:
    """[plot].sets as SetSpecs, in order: a selector alone names its folder (`"pdf=X"` → `pdf-X`, an index
    the point's own name later), a list is `set<k>` (its place), a table its `name` (`set<k>` when it has
    none), and a table's page keys as a figure's are. The named form (V167), `[plot.sets.<name>]`, is a table
    of them: each a set table, or a selector or list of them, named by its key. Shapes are checked here; what
    the selectors and filters match is chosen_points', resolve's and check_set's."""
    page_keys = set_page_keys()
    if isinstance(sets, dict):
        entries = []
        for name, entry in sets.items():
            if isinstance(entry, dict):
                if "name" in entry and entry["name"] != name:
                    raise HeimdallError(f"[plot.sets.{name}] is named by its key: it takes no name", where=f"{where}.{name}.name")
                entries.append({**entry, "name": name})
            else:
                entries.append({"name": name, "points": entry if isinstance(entry, list) else [entry]})
        sets = entries
    out = []
    for k, entry in enumerate(sets or [], start=1):
        at = f"{where}[{k}]"
        spec = SetSpec("", where=at)
        if isinstance(entry, dict):
            unknown = sorted(set(entry) - set(SET_KEYS) - set(page_keys))
            if unknown:
                raise HeimdallError(f"a set takes no '{unknown[0]}'", where=at,
                               hint=did_you_mean(unknown[0], [*SET_KEYS, *page_keys]) or
                               f"a set's keys: {', '.join(SET_KEYS)}, and [plot]'s page keys")
            name = entry.get("name", f"set{k}")
            if not isinstance(name, str) or not name:
                raise HeimdallError("a set's name is its folder: a string", where=f"{at}.name")
            selectors = entry.get("points", [])
            if not isinstance(selectors, list):
                raise HeimdallError("a set's points are a list of selectors", where=f"{at}.points")
            spec.pages = _pages_shape(entry["pages"], f"{at}.pages") if "pages" in entry else None
            curves = entry.get("curves", [])
            curves = [curves] if isinstance(curves, dict) else curves
            if not isinstance(curves, list):
                raise HeimdallError("a set's curves are a filter, { quantity = … }, or a list of them", where=f"{at}.curves")
            spec.curves = [_filter_shape(c, f"{at}.curves[{i}]", styled=True) for i, c in enumerate(curves, start=1)]
            spec.reference = _filter_shape(entry["reference"], f"{at}.reference") if "reference" in entry else None
            spec.look = _look_shape(entry["look"], f"{at}.look") if "look" in entry else None
            spec.keys = {key: value for key, value in entry.items() if key not in SET_KEYS}
            schema.check(spec.keys, "figure", at, only=page_keys)
            if not selectors and not spec.axes:
                raise HeimdallError("a set names its points: points = […], pages = { … } or curves = { … }", where=at,
                               hint='{ name = "lo", pages = { generator = "all" }, curves = { pdf = ["a", "b"] } }')
            if not spec.axes and (spec.reference or spec.look):
                raise HeimdallError("reference and look are a set's with pages or curves", where=at,
                               hint="a set of points alone draws them in the order named: the first is the reference")
            named = set(spec.pages or {}) & {q for c in spec.curves for q in c}
            if named:
                raise HeimdallError(f"a set names {sorted(named)[0]} in both pages and curves", where=at,
                               hint="an axis makes pages or curves, not both")
        elif isinstance(entry, list):
            name, selectors = f"set{k}", entry
            if not selectors:
                raise HeimdallError("a set names at least one point", where=at)
        else:
            name, selectors = None, [entry]
        for item in selectors:
            if isinstance(item, bool) or not isinstance(item, (int, str)) or item == "" or (isinstance(item, int) and item < 1):
                raise HeimdallError("a set's points are 1-based indices, names, globs, tags, \"quantity=tag\" or \"all\"",
                               where=at, hint=f"got {item!r}")
        if name is None:
            name = re.sub(r"[^A-Za-z0-9._+-]+", "-", str(entry)).strip("-") or f"set{k}"
            name = f"#{entry}" if isinstance(entry, int) else name      # the point's name, once it is known
        if "/" in name or name in (".", "..", "index.html", *RESERVED_SETS):
            raise HeimdallError(f"a set's folder may not be {name!r}", where=at,
                           hint=f"{', '.join(RESERVED_SETS)} are the backends' folders" if name in RESERVED_SETS else None)
        spec.name, spec.selectors = name, list(selectors)
        out.append(spec)
    names = [s.name for s in out]
    clashes = sorted({n for n in names if names.count(n) > 1})
    if clashes:
        raise HeimdallError(f"two sets share the folder {clashes[0]}", where=where, hint='name them: { name = "…", points = […] }')
    return out


#: What a styled value of a curves filter holds besides its tag (or value): its curves' look …
STYLE_KEYS = ("colour", "line", "width")
#: … and a styled list of values besides its tags: their looks, in their order.
LIST_KEYS = {"colours": "colour", "lines": "line", "widths": "width"}
#: The spellings a styled value may use for these.
SPELLINGS = {"color": "colour", "colors": "colours"}


#: The set every plot document holds (V167): the whole run, as a page grid that reads well.
TOTALITY = "totality"


def named_sets(sets) -> dict:
    """[plot].sets in the named form (V167): {name: its table}, in order; a V159 entry is { points = […] }."""
    if not sets or sets == schema.DEFAULT:
        return {}
    if isinstance(sets, dict):
        return dict(sets)
    out = {}
    for spec, entry in zip(set_entries(sets, "[plot].sets"), sets):
        out[spec.name] = {k: v for k, v in entry.items() if k != "name"} if isinstance(entry, dict) else {"points": spec.selectors}
    return out


def totality(configuration, members: list, values=None) -> dict:
    """The totality set's table (V167, the user's rule): every point, nothing excluded. With plot_points, its pages
    along them and its curves along the rest; else its curves along the axis whose number of values among the
    members is in 4–7 and closest to 5 (none in 4–7: the closest to 5; a tie: the earlier in vary), its pages
    along every other axis that takes several values. An entangled group is one axis, named by its first
    quantity; listed points one, named by all its quantities. Combined axes are no axis."""
    combined = set(configuration.combine)
    groups = [g for g in axes(configuration) if not set(g) & combined]

    def names(group) -> list[str]:
        return list(group) if isinstance(group, Listed) else [group[0]]

    def count(group) -> int:
        return len({group_key(group, getattr(m, "point", m).choice) for m in members})

    if configuration.plot_points:
        paged, curved = split_axes(configuration)
        pages = [g for g in paged if not set(g) & combined]
        curves = [g for g in curved if not set(g) & combined]
    elif groups:
        counts = [count(g) for g in groups]
        pool = [i for i, n in enumerate(counts) if 4 <= n <= 7] or list(range(len(groups)))
        best = min(pool, key=lambda i: (abs(counts[i] - 5), i))
        curves = [groups[best]]
        pages = [g for i, g in enumerate(groups) if i != best and counts[i] > 1]
    else:
        return {"points": ["all"]}
    table = {}
    if pages:
        table["pages"] = {q: "all" for g in pages for q in names(g)}
    if curves:
        table["curves"] = {q: "all" for g in curves for q in names(g)}
    return table or {"points": ["all"]}


#: What a set's pages may be for none at all (V178): a page per object, every curve on it.
NO_PAGES = ("none", [], {})


def _pages_shape(pages, where: str) -> dict:
    """A set's pages as written: a filter, or NO_PAGES (as {})."""
    if any(pages == none and type(pages) is type(none) for none in NO_PAGES):
        return {}
    if not isinstance(pages, dict):
        raise HeimdallError("a set's pages are a filter, { quantity = … }, or \"none\" (a page per object, every curve on "
                       "it)", where=where, hint='pages = { generator = "all" }, or pages = "none"')
    return _filter_shape(pages, where)


def _filter_shape(table, where: str, styled: bool = False) -> dict:
    """A filter as written: {quantity: "all" | a tag or glob | "!tag" | a number | a list of those}. In a
    curves filter (`styled`) a value may be a table, { tag = "pdf1", colour = "#d62728", line, width } (or
    `value = <number>` for the tag): the look of the curves this filter draws with it; or several values with
    theirs, in order, { tags = "all" | […] | "<glob>" (or all = true), colours = […], lines = […], widths = […] }.
    `color` and `colors` are `colour` and `colours`."""
    if not isinstance(table, dict) or not table:
        raise HeimdallError("a filter is a table of quantities: { pdf = [\"a\", \"b\"], generator = \"all\" }", where=where)
    out = {}
    for name, what in table.items():
        items = []
        for item in what if isinstance(what, list) else [what]:
            if isinstance(item, dict):
                if not styled:
                    raise HeimdallError(f"{name}: a value with its own look is a curves filter's", where=f"{where}.{name}",
                                   hint='curves = { pdf = [{ tag = "pdf1", colour = "#d62728" }, "pdf2"] }')
                item = {SPELLINGS.get(k, k): v for k, v in item.items()}
                if item.get("all") is True and "tags" not in item:
                    item = {"tags": "all", **{k: v for k, v in item.items() if k != "all"}}
                if "tags" in item:                   # several values, their looks in order
                    if set(item) - {"tags", *LIST_KEYS} or len(item) < 2 or \
                            not all(isinstance(item[k], list) and item[k] for k in LIST_KEYS if k in item):
                        raise HeimdallError(f"{name}: values with their looks are {{ tags = \"all\" | […], colours = […], "
                                       "lines = […], widths = […] }", where=f"{where}.{name}", hint=f"got {item!r}")
                    for key, one in LIST_KEYS.items():
                        for k, look in enumerate(item.get(key, []), start=1):
                            check_curve_style({one: look}, f"{where}.{name}.{key}[{k}]")
                    items.append(item)
                    for tag in item["tags"] if isinstance(item["tags"], list) else [item["tags"]]:
                        if isinstance(tag, bool) or not isinstance(tag, (int, float, str)) or tag == "":
                            raise HeimdallError(f"{name}: tags are tags, globs, \"all\" or numbers", where=f"{where}.{name}",
                                           hint=f"got {tag!r}")
                    continue
                tagged = [k for k in ("tag", "value") if k in item]
                if len(tagged) != 1 or set(item) - {*tagged, *STYLE_KEYS} or len(item) < 2:
                    raise HeimdallError(f"{name}: a value with its own look is {{ tag = \"<tag>\", colour, line, width }}",
                                   where=f"{where}.{name}", hint=f"got {item!r}")
                check_curve_style({k: v for k, v in item.items() if k in STYLE_KEYS}, f"{where}.{name}")
                items.append(item)
                item = item[tagged[0]]
            else:
                items.append(item)
            if isinstance(item, bool) or not isinstance(item, (int, float, str)) or item == "":
                raise HeimdallError(f"{name}: a filter's values are \"all\", tags, globs, \"!tag\" or numbers",
                               where=f"{where}.{name}", hint=f"got {item!r}")
        if isinstance(what, list) and not what:
            raise HeimdallError(f"{name}: a filter names at least one value", where=f"{where}.{name}", hint='"all": every one')
        out[name] = items if isinstance(what, list) else items[0]
    return out


def _bare(item) -> list:
    """A filter's value without its look: a styled value's tag (or value), a styled list's tags."""
    if not isinstance(item, dict):
        return [item]
    if "tags" in item:
        return item["tags"] if isinstance(item["tags"], list) else [item["tags"]]
    return [item.get("tag", item.get("value"))]


def value_styles(run, name: str, what, where: str) -> dict[int, dict]:
    """A curves filter's styled values for one quantity: value index → the look its table gives (a styled
    list's i-th look to its i-th value; fewer looks than values is refused)."""
    out = {}
    for item in what if isinstance(what, list) else [what]:
        if not isinstance(item, dict):
            continue
        indices = resolve(run, name, _bare(item), where)
        if "tags" in item:
            for key, one in LIST_KEYS.items():
                given = item.get(key)
                if given is None:
                    continue
                if len(given) < len(indices):
                    tags = ", ".join(tag_of(run.quantities[name], i) for i in indices)
                    raise HeimdallError(f"{name}: {len(given)} {key} for {len(indices)} values ({tags})", where=f"{where}.{name}",
                                   hint=f"one each, in that order; fewer would repeat: give {len(indices) - len(given)} more")
                for index, look in zip(indices, given):
                    if look != schema.DEFAULT:
                        out[index] = {**out.get(index, {}), one: look}
            continue
        look = {k: v for k, v in item.items() if k in STYLE_KEYS and v != schema.DEFAULT}
        for index in indices:
            out[index] = {**out.get(index, {}), **look}
    return out


def _look_shape(look, where: str):
    if look == "palette":
        return look
    if not isinstance(look, dict) or not look or set(look) - {"colour", "line"} or \
            not all(isinstance(v, str) and v for v in look.values()):
        raise HeimdallError('look is { colour = "<quantity>", line = "<quantity>" } (either or both), or "palette"', where=where)
    if look.get("colour") and look.get("colour") == look.get("line"):
        raise HeimdallError("look gives one quantity both the colour and the line", where=where)
    return dict(look)


def values_of(member) -> dict:
    """quantity → value index of a member: a plan's or a recorded member's values (swept and fixed), or a
    sweep Point's choice."""
    values = getattr(member, "values", None)
    return values if isinstance(values, dict) else getattr(member, "point", member).choice


def resolve(run, name: str, what, where: str) -> list[int]:
    """A filter's value for one quantity as its value indices, in the order written: "all" (the quantity's
    order), a tag, a glob of tags, a number (a value equal to it), a list of those; "!tag" leaves values out
    (a list of only those: every other value). A tag or glob naming no value is refused, with the tags."""
    if name not in run.quantities:
        raise HeimdallError(f"a set names '{name}', which is not a quantity", where=where,
                       hint=did_you_mean(name, list(run.quantities)) or f"quantities: {', '.join(run.quantities)}")
    quantity = run.quantities[name]
    tags = [tag_of(quantity, i) for i in range(len(quantity.values))]
    items = [bare for i in (what if isinstance(what, list) else [what]) for bare in _bare(i)]
    kept: list[int] = []
    dropped: set[int] = set()
    for item in items:
        negated = isinstance(item, str) and item.startswith("!")
        item = item[1:] if negated else item
        if item == "all":
            found = list(range(len(tags)))
        elif isinstance(item, (int, float)):
            found = [i for i, v in enumerate(quantity.values)
                     if isinstance(v, (int, float)) and not isinstance(v, bool) and v == item]
        elif any(c in item for c in "*?["):
            found = [i for i, t in enumerate(tags) if fnmatch.fnmatchcase(t, item)]
        else:
            found = [i for i, t in enumerate(tags) if t == item]
        if not found:
            raise HeimdallError(f"a set names {name} = {item!r}, which is no value of it", where=where,
                           hint=" ".join(filter(None, [did_you_mean(str(item), tags), f"{name}: {', '.join(tags)}"])))
        if negated:
            dropped |= set(found)
        else:
            kept += [i for i in found if i not in kept]
    if not any(not (isinstance(i, str) and i.startswith("!")) for i in items):
        kept = list(range(len(tags)))                        # only exclusions: every other value
    return [i for i in kept if i not in dropped]


@dataclass
class Cell:
    """A page cell of a set (V163): its folder under the set's ("" for one cell), its text ({cell}), its
    members in curve order, the groups that label its curves, each curve's look ({point name: style}) and the
    set's look (role → quantity)."""
    key: str
    text: str
    members: list
    labelled: list
    looks: dict = field(default_factory=dict)
    roles: dict = field(default_factory=dict)


def set_cells(run, members: list, spec: SetSpec, palette=(), *, values=values_of, looked=()) -> tuple[list[Cell], list[str]]:
    """A V163 set's page cells from these members (in point order), and what the plot stage says of them.
    The members are those that match `points` (if any), `pages` and one of `curves` (none: every member);
    a cell per combination of the page axes present, in the order written (\"all\": the quantity's); its
    curves each curve filter in turn, by the order its values are written (its first key outermost), then
    point order; a member two filters match is drawn once. A swept quantity neither names, taking several
    values, pages too (a page per value; said), but with `pages = "none"` (V178) it joins the curves: nothing
    pages. `reference` moves the curve it matches first. The look:
    `look`'s colour axis takes `palette` by the value's place in the set (the same on every page), its line
    axis CURVE_LINES; with no look, two varying curve axes, one with at most 4 values: that one the line. A
    curves filter's styled value ({ tag, colour, line, width }) gives the curves it draws their look, over the set's."""
    where = spec.where
    picked = list(members)
    if spec.selectors:
        picked = []
        for selector in spec.selectors:
            try:
                found = chosen_points(run, members, selector, where)
            except HeimdallError:                          # its points are not complete (plan time names a typo)
                found = []
            picked += [m for m in found if m not in picked]
        if spec.axes:                                 # a filter then: the curves' order is theirs
            picked.sort(key=members.index)
    pages_ = {q: resolve(run, q, what, f"{where}.pages") for q, what in (spec.pages or {}).items()}
    curves = [{q: resolve(run, q, what, f"{where}.curves") for q, what in c.items()} for c in spec.curves]
    styled = [{q: value_styles(run, q, what, f"{where}.curves") for q, what in c.items()} for c in spec.curves]

    every = {q: len(run.quantities[q].values) for flt in [pages_, *curves] for q in flt}

    def matches(m, flt) -> bool:                      # "all" takes a point a listed row leaves without the quantity
        got = values(m)
        return all(got.get(q) in indices or (got.get(q) is None and len(set(indices)) == every[q])
                   for q, indices in flt.items())

    picked = [m for m in picked if matches(m, pages_)]
    own: dict[str, dict] = {}                         # a curve's look from its filter's styled values
    if curves:
        ordered = []
        for flt, looks_of in zip(curves, styled):
            mine = [m for m in picked if m not in ordered and matches(m, flt)]
            mine.sort(key=lambda m: tuple(flt[q].index(values(m)[q]) for q in flt))      # stable: point order next
            for m in mine:
                style = {k: v for q in flt for k, v in looks_of[q].get(values(m)[q], {}).items()}
                if style:
                    own[getattr(m, "point", m).name] = style
            ordered += mine
        picked = ordered
    notes = []
    quantities = run.quantities                       # a compound's later fields ride with its first (V186):
    swept = list(dict.fromkeys(q for m in picked for q in getattr(m, "point", m).choice    # never an axis of their own
                               if not getattr(quantities.get(q), "silent", False)))
    named = set(pages_) | {q for flt in curves for q in flt}

    def varies(q, among) -> bool:
        return len({values(m).get(q) for m in among}) > 1

    paged = spec.pages != {}                          # pages = "none" (V178): no axis pages, not even the unnamed
    loose = [q for q in swept if q not in named and varies(q, picked)] if curves else []
    extra = loose if paged else []
    if extra:
        notes.append(f"set {spec.name}: {', '.join(extra)} " + ("is" if len(extra) == 1 else "are")
                     + " named by neither pages nor curves and take" + ("s" if len(extra) == 1 else "")
                     + " several values: a page each")
    page_axes = list(pages_) + extra
    curve_axes = list(dict.fromkeys([q for flt in curves for q in flt] + ([] if paged else loose))) if curves else \
        [q for q in swept if q not in page_axes]

    def order_of(q, index):
        return pages_[q].index(index) if q in pages_ else index

    cells: dict[tuple, list] = {}
    for m in picked:
        cells.setdefault(tuple(values(m).get(q, -1) for q in page_axes), []).append(m)
    keys = sorted(cells, key=lambda key: tuple(order_of(q, i) for q, i in zip(page_axes, key)))
    look = _look_of(run, spec, curve_axes, picked, values, looked)
    slots = {role: look_slots(q, picked, values) for role, q in look.items()}
    out = []
    reference = {q: resolve(run, q, what, f"{where}.reference") for q, what in (spec.reference or {}).items()}
    missed = []
    for key in keys:
        mine = cells[key]
        if reference:
            first = next((m for m in mine if matches(m, reference)), None)
            if first is None:
                missed.append(key)
            else:
                mine = [first] + [m for m in mine if m is not first]
        name = "_".join(tag_of(quantities[q], i) for q, i in zip(page_axes, key) if i != -1)
        text = ", ".join(label_of(quantities[q], i) for q, i in zip(page_axes, key) if i != -1)
        differ = [q for q in curve_axes if varies(q, mine)] or [q for q in curve_axes if varies(q, picked)] or curve_axes
        looks = {}
        for m in mine:
            style = {}
            for role, q in look.items():
                slot = slots[role].get(values(m).get(q))
                if slot is None:
                    continue
                if role == "colour" and palette:
                    style["colour"] = palette[slot % len(palette)]
                elif role == "line":
                    style["line"] = CURVE_LINES[slot % len(CURVE_LINES)]
            style.update(own.get(getattr(m, "point", m).name, {}))       # a value's own look over the set's
            if style:
                looks[getattr(m, "point", m).name] = style
        out.append(Cell(name, text or spec.name, mine, [[q] for q in differ], looks, dict(look)))
    if missed:
        notes.append(f"set {spec.name}: reference matches no curve on {len(missed)} of {len(keys)} page cell(s): "
                     "their first curve is the reference")
    alike = []                                        # curves on one page with the same colour and line
    for cell in out:
        seen: dict[tuple, str] = {}
        for m in cell.members:
            got = cell.looks.get(getattr(m, "point", m).name, {})
            key = (got.get("colour"), got.get("line", "solid"), got.get("width"))
            if got.get("colour") is None:
                continue
            if key in seen:
                alike.append((cell.key, seen[key], getattr(m, "point", m).name))
            seen.setdefault(key, getattr(m, "point", m).name)
    if alike:
        cell, a, b = alike[0]
        notes.append(f"set {spec.name}: {len(alike)} curve(s) look like another on its page ({a} and {b}"
                     + (f" on {cell}" if cell else "") + "): give them colours of their own, or the set a longer palette, "
                     "style = { curves = { palette = [\"#rrggbb\", …] } }")
    return out, notes


def check_set(run, spec: SetSpec, points: list, combined=(), *, values=values_of) -> None:
    """At plan time (V163): a set table's filters name quantities of the configuration's points (swept or
    fixed, not combined away), each value they name is a value some point has, and its look names curve
    axes, the line one with at most len(CURVE_LINES) values among the set's points."""
    present: dict[str, set] = {}
    for m in points:
        for q, i in values(m).items():
            present.setdefault(q, set()).add(i)
    filters = [("pages", spec.pages or {})] + [(f"curves[{k}]", c) for k, c in enumerate(spec.curves, 1)] + \
        [("reference", spec.reference or {})]
    for at, flt in filters:
        for q, what in flt.items():
            here = f"{spec.where}.{at}.{q}"
            resolve(run, q, what, here)                   # its quantity and tags
            if q in combined:
                raise HeimdallError(f"a set names {q}, which the configuration combines away", where=here,
                               hint="its points are merged over it: name another axis")
            if q not in present:
                raise HeimdallError(f"a set names {q}, which no point of the configuration sets", where=here,
                               hint="vary it or fix it in the configuration, or leave it out of the set")
            if at.startswith("curves"):
                value_styles(run, q, what, here)             # a styled list's looks: one per value
            quantity = run.quantities[q]
            named = [b for item in (what if isinstance(what, list) else [what]) for b in _bare(item)
                     if not (isinstance(b, str) and (b == "all" or b.startswith("!") or any(c in b for c in "*?[")))]
            for one in named:                             # a tag or number named alone is a value some point has
                if not set(resolve(run, q, one, here)) & present[q]:
                    shown = [tag_of(quantity, i) for i in sorted(present[q])]
                    raise HeimdallError(f"a set names {q} = {one!r}, which no point of the configuration has",
                                   where=here, hint=f"its points have {q}: {', '.join(shown)}")
    if isinstance(spec.look, dict):
        cells, _ = set_cells(run, points, spec, values=values)
        picked = [m for c in cells for m in c.members]
        curve_axes = [q for flt in spec.curves for q in flt] + (list(present) if spec.pages == {} else []) \
            if spec.curves else [q for q in present if q not in (spec.pages or {})]
        for role, q in spec.look.items():
            if q not in curve_axes:
                raise HeimdallError(f"look's {role} is {q}, which is not one of the set's curve axes", where=f"{spec.where}.look",
                               hint=f"its curve axes: {', '.join(dict.fromkeys(curve_axes)) or 'none'}")
        line = spec.look.get("line")
        if line and len(look_slots(line, picked, values)) > len(CURVE_LINES):
            raise HeimdallError(f"look's line is {line}, which takes {len(look_slots(line, picked, values))} values in the set: "
                           f"there are {len(CURVE_LINES)} line styles", where=f"{spec.where}.look",
                           hint="give the line to an axis of at most 4 values, and the colour to this one")


def _look_of(run, spec: SetSpec, curve_axes: list, picked: list, values, looked=()) -> dict[str, str]:
    """role → quantity: the set's look, or with none the automatic one (V163): two curve axes varying in the
    set, neither with styles of its own (V67), one with at most len(CURVE_LINES) values: it takes the line style,
    the other the colour."""
    if spec.look == "palette":
        return {}
    if isinstance(spec.look, dict):
        return dict(spec.look)
    varying = [q for q in curve_axes if len({values(m).get(q) for m in picked}) > 1]
    if len(varying) != 2 or any(run.quantities[q].styles or q in looked for q in varying):   # V171: [plot.looks] too
        return {}
    counts = {q: len({values(m).get(q) for m in picked}) for q in varying}
    line = min(varying, key=lambda q: (counts[q], varying.index(q)))
    if counts[line] > len(CURVE_LINES):
        return {}
    return {"colour": next(q for q in varying if q != line), "line": line}


def look_slots(q: str, picked: list, values) -> dict[int, int]:
    """A look axis's value index → its slot: its place among the set's values, in curve order."""
    seen = list(dict.fromkeys(values(m).get(q) for m in picked if values(m).get(q) is not None))
    return {index: slot for slot, index in enumerate(seen)}


def chosen_points(run, point_list: list, selector, where: str) -> list:
    """What one selector of a set names, in point order: a 1-based index, "all", a point's name, a glob of
    names, "quantity=tag", or a tag of any swept or fixed quantity's (every point with it). `point_list`
    holds sweep Points, or anything with a `.point` that is one. An unknown selector is refused."""
    def point(m):
        return getattr(m, "point", m)

    if isinstance(selector, int):
        found = [m for m in point_list if point(m).index == selector]
    elif selector == "all":
        found = list(point_list)
    elif "=" in selector:
        name, _, wanted = selector.partition("=")
        if name not in run.quantities:
            raise HeimdallError(f"a set names '{selector}', and '{name}' is not a quantity", where=where,
                           hint=did_you_mean(name, list(run.quantities)))
        found = [m for m in point_list if name in point(m).choice and tag_of(run.quantities[name], point(m).choice[name]) == wanted]
    elif any(c in selector for c in "*?["):
        found = [m for m in point_list if fnmatch.fnmatchcase(point(m).name, selector)]
    else:
        found = [m for m in point_list if point(m).name == selector] or \
                [m for m in point_list if any(tag_of(run.quantities[q], i) == selector
                                              for q, i in point(m).choice.items() if q in run.quantities)]
    if not found:
        raise HeimdallError(f"a set names '{selector}', which matches no point", where=where,
                       hint=", ".join(point(m).name for m in point_list[:6]) + (", …" if len(point_list) > 6 else ""))
    return found
