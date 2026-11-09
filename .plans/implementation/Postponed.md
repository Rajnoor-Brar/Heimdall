# Postponed

Items read in round 1's planning (2026-11-09) and left for a later round: the next planning's input. Each says what it is, what it waits on, and **decision** where the developer must choose first. The full text of an audit finding is in git, in round 1's first commit (P0.1), at `.plans/audits/2026-11-08-code/`. An item that is also an issue names it, and `ISSUES.md` owns that issue. This list adds only what the issue lacks.

Kept until a round builds an item or the developer drops it. The next planning moves the items it targets into its own plan, and deletes them here.

## First: one dialect (D-1, I-20, I-21)

- **The work:** v3 becomes the form and the model. The fixtures move first (`heimdall migrate --v3`, each fixture together with its test). Then the model takes v3's names, with `identity_parts` mapping to the frozen v2 keys (the golden file proves nothing reruns). Then `v3.py`, the v2 branches and `run.schema.json` are deleted. The issues behind it: I-25, I-26, I-35 and I-70.
- **Riding with it:**
  - G-2: a v3 file without `[file]`, `[cfgs]` or a chain is read as v2 (`v3.is_v3`, `v3.py:66`);
  - R-7 and T-2: all 11 fixtures are v2;
  - R-8: `migrate.py`'s ten one-shot migrations, with no record of which work dir still needs which. Dry runs over both real work dirs, read only, with the developer's yes;
  - S-5: `config.parse`, 261 lines and 112 branches, split after.
- **The question to settle first (found 2026-11-09):** every older Run's snapshot (`records/…/<R>/config/`) is a v2 file, and `plot`, `status`, `runs --resume` and `--again` read it. A loader that refuses v2 breaks every old record. Three ways out:
  - keep a snapshot-only v2 reader;
  - migrate records' snapshots, which writes into work dirs and so needs the developer's yes;
  - refuse old records with a way on.

## From the audit of 2026-11-08

**Dead and retired**
- **R-4, R-5, O-8:** retired forms are refused in seven places, each with its own message and no end date, and two commands exist only as stubs (`stats`, `deck`). The move is `runner/retired.py`, `{old: (new, since, kind)}`, read by every site (I-26). **Decision:** a date or a removal rule per retirement (30 days, the next tag), since Heimdall has no releases.
- **Sweeps:**
  - private helpers used once (inline the pass-throughs);
  - keyword arguments and `if` arms no caller reaches (`run_one`, `_cmd_run`, `plot._pages`);
  - each tool folder against a test that runs it;
  - shell functions against their callers (I-25's list);
  - `src/` C++ flags against the Python that passes them;
  - `sweeps/defs.py` per class, with receivers.

**Duplication**
- **D-2, decision:** five ways to merge points:
  - `combine`;
  - the `merge` post tool;
  - `plotmerge`;
  - the `merged` figure;
  - a set's `merge` and `band`.

  The proposal: a set's `merge` is the one merge at drawing time, the `merged` figure becomes a set (with I-41), and `combine` stays the recorded merge. Asked of the developer: is there a use of the `merge` post tool that `combine` does not cover? Is `plotmerge` renamed `bundle`?
- **D-4:** HTML pages written five ways (`plot.write_index`, `write_sets_index`, `report._index`, `figures/webpage.py`, `viewer.py`). One helper (I-44).
- **D-7:** ten polling loops with their own sleeps. A `runs.wait_for(predicate, every, deadline)` where they wait on the registry.
- **Sweeps:**
  - bodies that are copies (AST-normalised), starting with `house`'s `_*_lines` and `report`'s `_*_section`;
  - flags that mean the same (I-70);
  - help texts that list choices the code also lists;
  - which numbers Paint and `stats/` both compute, now that `stats/` reads the measured bins (see stats-backend below).

**Structure**
- **S-1:** split `cli.py` (3579 lines) into a `runner/cli/` package (I-50). T-3 rides with it: re-point the 14 `monkeypatch.setattr(cli, …)` to the owning modules.
- **S-2:** split `house.py` (1313 lines): `listing.py`, `show.py`, and `house` keeps `ls`, `explain`, `status` and `clean` (the library left at round 1's P3).
- **S-4:** `record.py`, nine subjects. A small, frozen `identity.py`, with locks, attempts, the manifest and labels in their own modules. Identity is ask-first territory: plan it with the developer.
- **S-6:** split `report.py` (2443 lines) into a `runner/report/` package: `sources`, `recipe`, `plan`, `layout` and `tex`.
- **S-7:** the longest functions. First `plot._pages` (272 lines, 150 branches) and `plotdoc.load_across` (143 lines, 112 branches): name their stages.
- **S-8:** `runner/` as subpackages (I-50).
- **Sweeps:**
  - the import graph's fan-in and fan-out;
  - the cohesion of `tools.py` and `plot.py`;
  - whether `bars.py` only draws now.

**Design**
- **G-4:** a frozen `RunRequest` that `build_plans` takes, instead of forged `argparse.Namespace`s (11 in `cli.py`; I-35). It needs no wait for I-25.
- **G-5:** four control channels to a running worker. One `runs/<id>.ask.json` and one signal for every non-destructive ask. E-6 (a two-way watch socket) builds on it.
- **G-6:** 52 imports inside functions in `cli.py`. After S-1, only numpy, yoda, matplotlib and `stats` stay lazy.
- **G-7:** a `V<n>` cite may outlive its decision. The fix: `heimdall docs --drift` flags a cite of a superseded note.
- **Sweeps:**
  - keys read, then ignored (F-2 is one);
  - silent fallbacks (`or {}`, `getattr(args, x, None)`);
  - module-level caches a long worker sees stale;
  - writes that bypass `write_atomic`.

**Oversights**
- **O-4, decision:** a sweep is a queue with a terminal and one process without (`--plain`, a pipe, cron). Either one model, or the difference stated in `heimdall run --help`.
- **O-5:** `flock` may be node-local on NFS or Lustre. Verify on the cluster (I-87), then `lockf`, or an `O_EXCL` lock file with host and pid.
- **O-9, decision, ask-first (= F-4):** the Herwig, MadGraph and Sherpa fixtures' identities hash an absolute `.cache/…` path. So a moved work dir reruns those points, and two clones' library entries do not pool. A cheaper alternative to weigh is stripping the path from the library key only, which leaves the identity alone and reruns nothing.
- **O-10, decision:** the implementer's scoring rules of 2026-11-07, each to accept as a decision note or reject as a fix:
  - weights precedence (figure `weight` > first glob > 1);
  - `mad`'s floor (10 % of the good-to-bad span);
  - `median` floored at `|good|`;
  - `promethee` q = 0.1, p = 1.0;
  - `topsis` as 1 − closeness;
  - `fisher`'s p capped at 1e-300;
  - data pages beating curve-measured pages in a mixed table;
  - no renormalisation of a merged file;
  - marginals over (cell, point) scores;
  - an Errand's row over only the pages every Run has.

  The defaults (the precedence, mixed references, the page intersection) matter first. The opt-in ones can wait.
- **Sweeps:**
  - free disk before a run, and `--plan`'s size estimate;
  - kill -9 during each write path;
  - two users on one Himinbjorg (the library and `forge/`);
  - clock and time zones in listings;
  - 10⁴ points, and 50 configurations queued.

**Expansions** (each needs a yes and a plan)
- **E-1's second half:** `heimdall runs --queued-to M` on a run already queued, moving it within or between queues.
- **E-2:** `notify = "command"`, so a detached run started over ssh can notify (mail, ntfy, a webhook, the user's choice).
- **E-3, E-4:** `heimdall plan` (I-36) with cost estimates from recorded attempts' durations and products' sizes.
- **E-5:** the library for combine groups and post stages, and across Assignments.
- **E-6:** a two-way watch socket (after G-5).
- **E-7:** mypy on `runs.py`, `record.py`, `RunEntry` and `RunRequest` (I-13).
- **E-8:** `heimdall du`.
- **E-9:** `--json` on `runs`, `status`, `ls` and `library list` (I-37).
- **Sweeps:** shell history (read only, with a yes); `HeimdallError` without a `hint`; commands without `-i` or `--json`.

**Tests**
- **T-4:** tests depend on their order through one scratch work dir (I-76).
- **Sweeps:**
  - mutation of `wait_turn`, `library_key` and `link_library`;
  - loosened assertions;
  - fakes of `PointPlan`, `Errand` and `Configuration` of the real type;
  - `--durations=10`.

**Process**
- **Sweeps:** every open `I-` against the code, as the 2026-11-02 rebuild did; memory files against the repo (preferences only).

## From the implementer's findings (`Implementation_Issues.md`, 2026-11-07/08)

- **F-2:** `[figure].weight` is accepted and checked, but the summary never reads it. Either read it, or refuse the key. Goes with O-10's precedence.
- **F-4:** see O-9.
- **F-11, decision:** the cells-against-curves table (`<metric>:crossed`) and the `area` column of `statistics.csv` were kept. Should either go?
- **F-12:** a real study's own config fails `heimdall check`. `[plot].sets[4].curves[1].pdf` names a PDF its `[quantities.pdf]` does not enable. It is the developer's file, never changed by Heimdall.

## From the plans of 2026-11-07

**stats-backend**
- **⏸ The developer reads one summary** (`statistics/<set>/summary.pdf` of a real Run) before the scoring is called right.
- **`heimdall plot --style-sync` does not sync `[score]`** (`write_chosen` leaves it as it is).
- **Whether Paint's totals can be dropped** now that Python's equal them (the plan's Always kept them "until phase 6 proves").

**points-library**
- **⏸ `heimdall library adopt` on a real work dir.** Deferred on 2026-11-08 until a work dir's 12-hour runs end. A script is ready outside the repo, in `~/heimdall-baselines/pre-adopt-20261108/`, with a dry run first. It writes into a work dir: the developer's yes.
- **`library = "only"` keeps the Run's `logs/` and `run.jsonl`**, looser than the plan's "no folder". **Decision:** accept, or give the entry a log home per Run.
- **Whether `results/` links are still needed** once every reader names the library through `points.json`. Contract later.
- **`record.FORMAT` stays 1.** To be taken up when a later change alters a reader's meaning of a key. The known cost: an older Heimdall takes a library point as stale.
- **An adopted Run's plot document** still names the old identities until it is written again.

## From earlier sessions

- **`heimdall migrate --plot-docs --apply`** on a real work dir: plot documents by tag. It needs the developer's yes.
