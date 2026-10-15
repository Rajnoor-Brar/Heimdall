# 02 — Plan

**Nothing here is built without the user's order, phase by phase.** Each phase names its findings, what
changes, and how it is checked. A finished step gets a V-row in docs/07_Record.md, as audit 3's did.

## Phase 1 — Small and certain (no decisions)

| Finding | Change |
|---|---|
| G1 | Delete `deck.deck_dir`, `plot.BACKENDS`, `figures/layout.TILED`, `tools.ENV`; use `setup.REFRESHED` in `refresh` (or delete it); `paths.forge_dir`, used by tests only, goes with its tests' lines |
| G2 | 05 §2's variables table: `HEP_PLAIN`, `NO_COLOR`, `APPTAINER_CONTAINER` / `SINGULARITY_CONTAINER` |
| G9 (H3, H8) | The hint at `cli.py:932` and `plot.py:1230`'s comment name `heimdall overlay`; `plot.objects_of`, `raws_of`, `_sha` and `base_of` inlined into their callers |
| G10 | bots/intent.md: F11–F13, CF4 closed; U5 says what exists; the header says what the file holds now |
| G12 | Messages in the file's own form: a v3 file's errors say `vary`, `fixed`, `chain`, `events` and `[cfgs.<name>]` (one table of v2 → v3 names, used where the message is made) |
| G17 | `{repo}` → `{hep}` in the recipes (`build_stack.py`'s placeholders, `standard.toml`) |

Checked by: the fast suite; a test that a v3 file's refusals name no v2 key (each C-rule's message).

## Phase 2 — Retirements and renames (decided by the user, 2026-10-15)

**The user's answers:** retire the finished migrations and old guards (G13, G14), the old entry points (G15,
G3) and the unused pieces (G5, G18, G16); **keep** the CI workflow and the Dockerfile (G4); **rename** the
marker `hep.toml` to `heimdall.toml` (G22); fix the messages but **keep reading v2** (G12, Phase 1); **mark**
unproven toolkits and keep them all (G7).

Checked before deciding: `heimdall migrate`, `--v3` and `--layout` (dry runs) over the machine's only work
dir found nothing to migrate, and nothing there uses a master, `plotmerge`, `HEKIT_*` or `{repo}`.

| Finding | Change |
|---|---|
| G13 | `migrate.py`: the v1 and v2-form rewrites go (`[master]` → `[config]`, `[run.cfgs]`, defaults, `{repo}` → `{work}`, figures, `formerly` tool names, exports), and `--layout` (`layout_moves`, `deck_moves`, `apply_layout`). What stays is the v2 → v3 rewrite: plain `heimdall migrate` does it (`--v3` accepted for a release), and the marker's rename (G22). `recipes/machine.py adopt`, `launch.sh`'s "adopt it" message, CLAUDE.md's "un-adopted stack" rule and recipes/README's in-checkout paths go. `labels.py`'s TLatex conversion goes if nothing reaches it (config refuses TLatex labels already) |
| G14 | The guards for `HEKIT_*` (`paths.check_retired`, `hep_env.sh`), `{repo}` (`tools.py`), the export keys (`tools.py` `RETIRED`), `HEP_SETUP`, and `[tool] formerly` (exec's `["custom"]`) go. The v2 → v3 key refusals stay while v2 is read |
| G15 | `heimdall doctor` and `heimdall status --stack` go: `heimdall stack doctor` and `heimdall stack status` are the names (an old command is refused with its new name for a release, from one table in `cli.py`). The shell's `quit`, `heimdall_cd`, `heimdall_refresh` and `heimdall_status` go (`heimdall quit`, `cd`, `refresh` and `stack status` stay). `recipes/platforms/mac/launch.sh` goes |
| G3 | `heimdall_stash`, `heimdall_forge` and `heimdall_stack` go; `heimdall_help` says what remains |
| G5 | The project master goes: `[file].master` / `[config].master` leaves the schema (an unknown key, refused by the schema with its did-you-mean), `quantities.load_master` reads the tool folders only, and its internal v1 shape (`{tool: {"compatible_quantities": …}}`) becomes `{tool: {quantity: mapping}}`. 04 §1–§3 and §8.1 say the tool folder (a work dir's own, `extends`) is how a mapping is changed |
| G18 | `framework/tools/plotmerge/` goes, with 05 §8 (05's later sections renumbered and every `05 §N` reference with them) and its test in `test_post.py`. `App_yd2rt --merge` stays: the plot stage uses it |
| G16 | `recipes/build_by_hand.txt` goes; recipes/README points to `build_stack.py --dry-run` |
| G22 | `heimdall.toml` marks a work dir: `heimdall setup` writes it; the walk up and `heimdall recognise` read `heimdall.toml`, then `hep.toml` (said, for a release); both in one folder is refused; `heimdall migrate` renames the marker (`git mv` in a repository). The template, the fixture (`tests/fixtures/work/hep.toml`, with the tests that read it), the docs (34 mentions) and CLAUDE.md follow. `$HEP`, `HEP_*`, `{hep}`, `hep_root()` stay, and 01 says once that they are Heimdall's |
| G7 | Each toolkit file may say `proven = ["<date> <platform> <base>", …]`, added by hand after a build the record shows (`@primary`, `@core-conda` today); `heimdall stack list --toolkits` and recipes/README §6 show "unproven" for the others. No toolkit or recipe is removed |
| G4 | Kept, by the user's choice. |

Checked by: the fast suite; the slow suite once; `heimdall migrate` and `heimdall setup` on a scratch work dir
with `hep.toml` (renamed, and read before the rename); the fixture's identities unchanged (the marker's name
is in no identity).

## Phase 3 — Finishing what is half-built

| Finding | Change |
|---|---|
| G6 | `heimdall cluster` with `[cluster] image`: plan inside the image, write `submit.sh` (sbatch lines chained by job id), run it on the host; `--status` and `--cancel` read its ids as now |
| G8 | After the user's comparison (R0): one 1D backend |
| G9 (rest) | Audit 2's R1–R3 (H2, H5–H7, H9, H10, H13–H16) |
| G19, G20 | A "which command" table in 00 and 05; a map of the stack's settings files in recipes/README §1 |

## Phase 4 — On the new machine

| Finding | Check |
|---|---|
| G11 | `@primary` from source on the conda base; the slow suite (the generators' tests among them); an Apptainer image of `@core-conda`; the Mac when it is next at hand |
| G23 | `heimdall doctor --record` on the new machine; the old row dated or dropped |

## Order

Phase 1, then Phase 2 (decided), each on the user's order. Phase 2's retirements shrink the code Phase 3
touches. Phase 4 follows the reinstall.
