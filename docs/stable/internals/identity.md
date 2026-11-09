---
id: identity
summary: what a point's identity hashes, how seeds follow from it, what skips a point and what reruns it
code: framework/runner/record.py, framework/runner/tools.py, framework/tools/pythia/tool.toml
---

# Identity and seeds

## Identity

A point's identity is a sha256 (`record.identity`) over what decides its result (`record.identity_parts`):

| Part | Holds |
|---|---|
| `threads`, `events`, `groups`, `prelim` | the point's size and the shape of its chain |
| `tools` | for each rendered tool, below |
| `seeds` | the seed rule: `"generator"`, `["manual", seed]` or `"random"` (`record.seed_rule`) |
| `upstream` | post stages: the identities of what they read |
| `products` | what a context file was asked to give |

Each rendered tool gives its tag, tool, `exe` and its sha256, `flags`, `options`, `config_values`, `base_sha256`, `card`, `argv`, plus `prepare`, `config`, `replica` and `files_sha256` when it has them.

- Card lines that repeat the base card's own value are left out, so restating a default does not rerun anything.
- `argv` is written with the point's folders as `{out}` and `{res}`, and all paths are made portable at the end of planning (`tools._portable_parts`), so moving Himinbjorg or a work dir reruns nothing (V137).
- The identity is computed before seeds are written into the cards, so there is no circularity.

**In no identity:** `serial` and every folder name (V12), `parallelism` (V36), and every plot setting, figure, style and `base.toml`. Those redraw, with `--only plot` or `heimdall plot`.

The parts are saved as `identity.json` beside `.complete`, and `heimdall run … --why` diffs them against today's plan (V57).

## Skipping

A point is complete when its `.complete` holds its identity (`record.is_complete`), and then it is skipped. `.complete` is written last, after the count checks, so a half-written point is never skipped. `record.stale` adds `--rerun`, and a resumed `--rerun` job's cut-off time, so what the paused job ran itself is not run again.

Identity is per point: every point runs its whole chain, and nothing is shared between points (V9), unless the errand asks for [the points library](#the-points-library). A sweep of a Rivet option regenerates the events each time; to avoid that, keep the events as a `[prelim]` file in one configuration and analyse them in another.

## The points library

`[errand] library = true` (or `"only"`) pools generation points per Assignment under a key that ignores the point's name, so two Errands that ask for the same physics run it once. The key (`library.key`, `library.parts`) is the sha256 of `identity_parts` without the card lines that start with each tool folder's `[card] comment` (where the point's name is: the card header), the seed rule kept: a manual seed is in the key, a random or generator seed is not. The identity itself is unchanged, so nothing reruns when the setting turns on, and the setting is in no identity or seed.

An entry is `records/<A>/library/<key16>/` (`.complete` holding the key, `identity.json`, `provenance.json`, `attempts.jsonl`, the lock) and `results/<A>/library/<key16>/`. A Run that uses it has relative links `points/<name>` → `../../../library/<key16>` in both trees, so every reader of those paths works as before, and a point complete in its entry is skipped for every Run whose key it is: `record.recorded_identity` returns the plan's own identity when the marker is the plan's key. A library point's seed is the entry's recorded one. The entry's lock (`record.lock_file`) lets one session run it whichever Run asks. A stage (pre, post, combined) is never pooled. `library.py` is the module; `record` never imports it. The command and the setting are in [outputs](../guide/outputs.md) and [scale](../guide/scale.md).

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

Anything in a point's identity reruns the points it touches, which costs generations: ask first ([invariants](../../rules/invariants.md)), and say so in the commit. Changing the seed basis moves every point's seeds.

`tests/golden/identity_parts.json` keeps `record.identity_parts` of every point of every fixture config (a point a line, keyed `<A>/<E>|<configuration>|<point>`), and `tests/runner/test_identity_golden.py` plans them all and compares, naming the point and the first key that differs. Binaries are masked (`exe_sha256`, and the `files_sha256` entries under `/build/`) so a rebuilt app does not fail it. Any change to what an identity hashes fails it; the file changes only with the developer's word and is never regenerated to pass. The parts of the Herwig, MadGraph and Sherpa fixture points hold an absolute path into the cache, so those identities depend on where the cache is (unlike the `{work}` and `{apps}` paths); the golden file masks it, and fixing it would be an identity change.

Why: [decisions](../design/decisions/identity.md).
