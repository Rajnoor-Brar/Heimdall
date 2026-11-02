---
id: identity
summary: what a point's identity hashes, how seeds follow from it, what skips a point and what reruns it
code: framework/runner/record.py, framework/runner/tools.py, framework/tools/pythia/tool.toml
---

# Identity and seeds

## Identity

A point's identity is a sha256 over what decides its result (`record.identity_parts`):

| Part | Holds |
|---|---|
| `threads`, `events`, `groups`, `prelim` | the point's size and the shape of its chain |
| `tools` | for each rendered tool, below |
| `seeds` | the seed rule: `"generator"`, `["manual", seed]` or `"random"` (`record.seed_rule`) |
| `upstream` | post stages: the identities of what they read |
| `products` | what a context file was asked to give |

Each rendered tool gives its tag, tool, `exe` and its sha256, `flags`, `options`, `config_values`, `base_sha256`, `card`, `argv`, plus `prepare`, `config`, `replica` and `files_sha256` when it has them.

- Card lines that repeat the base card's own value are left out, so restating a default does not rerun anything.
- `argv` is written with the point's folders as `{out}` and `{res}`, and all paths are made portable at the end of planning (`tools._portable_parts`), so moving the machine root or a work dir reruns nothing (V137).
- The identity is computed before seeds are written into the cards, so there is no circularity.

**In no identity:** `serial` and every folder name (V12), `parallelism` (V36), and every plot setting, figure, style and `base.toml`. Those redraw, with `--only plot` or `heimdall plot`.

The parts are saved as `identity.json` beside `.complete`, and `heimdall run … --why` diffs them against today's plan (V57).

## Skipping

A point is complete when its `.complete` holds its identity (`record.is_complete`), and then it is skipped. `.complete` is written last, after the count checks, so a half-written point is never skipped. `record.stale` adds `--rerun`, and a resumed `--rerun` job's cut-off time, so what the paused job ran itself is not run again.

Identity is per point: every point runs its whole chain, and nothing is shared between points (V9). A sweep of a Rivet option regenerates the events each time; to avoid that, keep the events as a `[prelim]` file in one configuration and analyse them in another.

## Seeds

Seeds follow the generator, not the point (V22). The **seed basis** (`record.seed_basis`) hashes the tools with `produces_events`, without their `argv` or card comments, plus threads and events. A detector simulation or analysis downstream does not move it, so one generator set-up gives the same events in any configuration, and a chain's point and an integrated program's compare bin for bin. `tests/runner/test_sweeps.py` pins this.

`base = lo + int(basis[:12], 16) mod (hi − lo + 1 − threads)`, and threads use `base … base + threads − 1`. `[lo, hi]` is the point's `seed_range`, from its seeded tools' `[card] seed_range`.

`record.assign_seeds` keeps blocks disjoint across a plan: a clash moves up by `threads`, in identity order, so no two points of one plan share events. Pythia does not check its own seeds (L4).

The seed reaches the tool through its folder's `[card]` lines (Pythia's are in its `tool.toml`), after the base card, so a seed set in a card never counts.

| `seed` key | Base | In the identity |
|---|---|---|
| `"identity"` | from the basis, above | `"generator"` |
| an integer, or a quantity targeting `<tool>/seed` | exactly that | `["manual", base]` |
| `"random"` | drawn when the point runs; a complete point keeps the one its `provenance.json` records, and `--rerun` draws again | `"random"` |

With manual seeds, two points of one generator set-up whose blocks overlap without being equal are refused: they would repeat some of each other's events. Every mode records the seed in `provenance.json` and `points.json`, so `heimdall reproduce` can repeat any point.

## Changing this code

Anything in a point's identity reruns the points it touches, which costs generations: say so in the commit. Changing the seed basis moves every point's seeds.

Why: [decisions](../design/decisions/identity.md).
