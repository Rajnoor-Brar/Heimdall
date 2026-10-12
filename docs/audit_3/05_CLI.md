# 05 — The command line and the shell

`hep` is good where it's careful:
- **`HepError`** prints what, where and a hint (196 of 311 raises give a hint), with did-you-mean for
  keys, sections, quantities, tools, configurations, vars and drops.
- **`hep check`** plans everything without running.
- **`--plan`, `--why` and `--show-config`** explain a run before it happens.

The problems are consistency, entry points and the shell around it.

---

## 1. One verb, several spellings — U60 (16)

- **"Show, don't do"** has seven spellings:
  - `build_stack.py --dry-run`/`-n`;
  - `hep run --plan` (and `--why`, `--show-config`);
  - `hep clean --dry-run`;
  - `hep cluster --dry-run`;
  - `hep migrate`, which is dry unless `--apply`;
  - `hep deck --list`;
  - `build_stack.py --list`.
- **Overrides:**
  - `key=value` and `pkg.key=value` for the build;
  - `--set KEY=VALUE` for `run` and `cluster`;
  - none for `check`, `status` and `clean`, so their view can differ from the run's.
- **Forcing work:** `--rerun` for runs; deleting a stamp file for the stack.
- **`--only`** is a stage for `run` but output targets for `deck`.
- **"status"** is three things:
  - `hep status` (points);
  - `hep status --stack` (versions);
  - `hep cluster --status` (jobs).

  The shell function `hep_status` (versions again, a different list) makes a fourth.
- **`--plain`** exists for three commands only.

**Proposed:**
- **`--dry-run`** everywhere (`--plan` kept as `run`'s alias);
- **`--set`** on every command that plans;
- **`--rebuild`** for the stack;
- **one `status` per noun:** `hep status` (points), `hep stack status`, `hep cluster status`;
- **`--plain`** global.

## 2. Two programs, two help systems — U59 (16), U61 (20)

- **`framework/bin/hep` is bash.** It dispatches most commands to Python, but parses `build` and
  `make` itself:
  - `hep build -j` with no number fails with "unbound variable" (`set -u`);
  - `--tests` in a work dir runs a target the work dir lacks;
  - `hep build --help` prints the global usage.
- **Two help systems:**
  - the bash `usage` text (`bin/hep:21-49`);
  - argparse.

  Subparsers set `help=` but no `description=`, so `hep run --help` has no description. `hep help run`
  prints the global usage. An unknown command gets the whole usage, with no did-you-mean.
- **`hep_help`** (the shell function) lists five commands.

**Proposed:** one Python entry point for every command, `build` and `make` included (bash only to
`exec` make). Then:
- a description for every subcommand;
- `hep help <command>` shows that command's help;
- an unknown command gets did-you-mean;
- the stack's builder joins as `hep stack build|list|doctor|status` over `recipes/build_stack.py`'s
  engine, with the same error format.

## 3. `hep` outside its environment — U57 (40)

`framework/bin/hep:59` runs whatever `python3` is first on `PATH`. Without the venv, every Python
subcommand dies before parsing, `--help`, `where` and `setup` included: `ModuleNotFoundError:
tomli_w` (`cli.py:27` → `cluster.py:35`). `bin/run` catches only `HepError`. This hits:
- cron;
- scripts;
- Slurm jobs. 05 §2 itself tells such shells to call `framework/bin/hep`, and `hep cluster`'s job
  scripts source `setup.sh` first only because of this.

**Proposed:**
- `bin/hep` runs the machine root's venv Python by path (`$HEP_MACHINE/venv/bin/python`), whatever
  the shell has loaded;
- a missing venv is one line: "no Python environment: build the stack (hep stack build) or set
  HEP_MACHINE".

## 4. From nothing to a first plot — U63 (28), U14

The README's path:
1. clone;
2. `python3 recipes/build_stack.py packages=@primary`;
3. `source setup.sh`;
4. `hep build --framework`;
5. `hep setup DIR --project P --git`.

Then the user is on their own. Where it breaks or stops:

| Step | What happens |
|---|---|
| build, on a Mac | "no apt-get" (`build_stack.py:452`): the Mac's path is `recipes/platforms/mac/build.sh`, which the README mentions only after |
| `source setup.sh`, in zsh (macOS's default shell) | half-loads (§5); the documented `load_hep` alias sources it directly, which is the zsh trap |
| after the build | no check step: nothing says whether the stack can do what Heimdall needs (`hep doctor`, 01 E) |
| `hep setup` | prints "added …" lines only (`setup.py:84`); the next steps are in the template's README and the starter's comments |
| the guide (02 §1.2) | goes from setup straight to `hep run`, skipping the `hep check` the template recommends |
| the guide's examples (02 §2 on) | use `Demo/jets`, which exists only in `tests/fixtures/work/`; the work-dir search skips `tests/` (`paths.py:116-119`), so `hep ls` there says "not inside a work dir", and nothing tells the reader to set `HEP_WORK` |

**Proposed:**
- **A README with one path per platform** (Linux, macOS, container), ending in a plot:
  `hep stack build @primary` → `hep doctor` → `hep setup ~/Study --example jets` → `hep check` →
  `hep run Demo/jets single` → `open results/…/plots/index.html`.
- **`hep setup --example <name>`** copies a working demo project (the fixture's configs, modules and
  dataset), so the guide's examples run in the reader's own work dir.
- **`hep setup` ends with the three next commands.**
- **`hep doctor`** is the bridge between "built" and "first run" (phase 2.1).

## 5. The shell environment — U58 (32), U34 (28)

`setup.sh` and `env/hep_env.sh`:
- **Bash only, unchecked.** It uses `${BASH_SOURCE[…]}`, `${!var}`, unquoted word-splitting loops,
  `<<<`, `$'…'` and `declare -F`, and nothing tests `$BASH_VERSION`. In zsh it fails part-way
  (`_hep_prepend: bad substitution`) and leaves a half-loaded shell.
- **The loaded check is an exported variable** (`HEP_ENV_LOADED`). A child of a half-loaded shell
  skips its setup ("already loaded"). Sourcing `stacks/<kit>/setup.sh` without `quit` changes
  `HEP_INSTALL` but keeps the other stack's `PATH`: C++20 headers with C++17 libraries.
- **`hep refresh` drops an isolated stack.** `HEP_SETUP` records the main `setup.sh`
  (`hep_env.sh:19`), and `quit` unsets `HEP_STACK`, so a refresh quietly reloads the default stack.
  This contradicts 05 §2 and V115, and no test covers it.
- **`quit` doesn't undo `env/machine.sh`'s lines.** `DYLD_LIBRARY_PATH` stays, and the GNU-tool
  entries pile up on each refresh.
- **The shell helpers duplicate commands:**

  | Helper | Overlap |
  |---|---|
  | `hep_status` | `hep status --stack`, with a different package set |
  | `hep_stash`, `hep_forge`, `hep_stack` | fixed paths, wrong for isolated stacks; `hep where` doesn't print them |
  | `hep_refresh` | `hep refresh` |
  | `hep_help` | `hep --help` |
- **Six package lists** (02 §2, U34). `hep_status` checks ONNX Runtime as `libonnxruntime.so`, which
  is wrong on a Mac.

**Proposed:**
- `setup.sh` refuses any shell but bash, before touching anything, and gives the way in
  (`launch.sh`, or `bash` then `source`).
- `launch.sh` becomes the documented `load_hep` on every platform.
- The loaded check tests the functions (`declare -F hep_refresh`), not only the variable.
- `quit` records and undoes `machine.sh`'s additions too.
- `refresh` reloads the setup that loaded the shell (stored per stack).
- The shell-only verbs go through the `hep` function, as `refresh` already does: `hep cd P`,
  `hep quit`. `hep_*` names stay as aliases for a release.
- One registry generates the environment's package list, `hep stack status` and `stack.toml` (phase
  3.2).

## 6. Error formats and words — U62 (16), U65 (9)

- **Four formats:**
  - `HepError` (what / where / hint);
  - argparse's `hep run: error: …`;
  - the bash dispatcher's;
  - the builder's red `error:`, which has no where, hint or did-you-mean.

  Plus raw tracebacks: `IncompleteRead`, `pkg.env=`, outside the venv.
- **Record ids in user-facing messages:**
  - "(V78)" in `--stack`'s help;
  - V93, V98, V99, V79, V65 and V81 in `config.py`'s errors;
  - C6/C7 in the guide's failure table;
  - "the v2 runner" in the CLI's description.

  A user must open `07_Record.md` to read an error.
- **A self-contradicting hint:** `cli.py:698` suggests `hep plot FILE…`, which `cli.py:692-694`
  refuses.
- **The manual is large:** the user pages are 02 (886 lines), 03 (597), 04 (1155) and 05 (967), and
  they cite record ids in prose. There is no one-page reference card.

**Proposed:**
- one error format for every command and the builder (what, where, hint, did-you-mean);
- record ids only after the message, as "(see V93)" for those who want the history, never in place
  of the explanation;
- a one-page `docs/00_Quick.md`: the layout, the ten commands, one run TOML annotated, where results
  are.
