# 02 — How the agents work

The protocol every agent follows while carrying out the phase files on a machine:
- who does what;
- where progress is kept;
- how a step is run and verified;
- when to stop and ask;
- how to report.

It is written for Claude Code, the user's tool, but nothing in it depends on Claude Code: a person
can follow the same files by hand. [README](README.md) §1 lists the phases; this page is the rule.

---

## 1. Starting on a fresh machine

The user does four things by hand, before any agent starts:

1. Install the OS, `git`, `python3` (3.11 or newer) and Claude Code.
2. Put the files kept before the wipe (01 §8) somewhere readable, such as a mounted disk.
3. Clone Heimdall:
   ```bash
   git clone https://github.com/Rajnoor-Brar/Heimdall.git ~/Github/Heimdall
   # or, before it is published, from the bundle kept before the wipe:
   git clone /path/to/kept/heimdall.bundle ~/Github/Heimdall && git -C ~/Github/Heimdall checkout main
   ```
4. Start Claude Code in `~/Github/Heimdall` and give it the start prompt (§11.1).

Everything after that is the orchestrator's. The plans are read from `~/Github/Heimdall/docs/framework/`
(`$HEP/docs/framework/`), and the deviations of §7 are committed there, so the next machine gets them.

---

## 2. Roles

| Role | Is | Does | Never |
|---|---|---|---|
| **Orchestrator** | the main session | reads the plans and the state; runs steps inline; starts the long jobs; asks at gates; writes `state.toml` and `log.md`; reports | marks a phase done without the verifier; works past a gate unanswered |
| **Builder** | a background process the orchestrator starts and watches (in Claude Code: a background shell plus a monitor on its log) | the long jobs only: the stack build (P1) and the slow test suite (P2) | runs anything interactive; asks for sudo; it inherits no approvals |
| **Verifier** | a fresh agent with no shared context (in Claude Code: a subagent), read-only | re-runs a phase's verification rows exactly as written and returns the table of §5.3 | edits, builds or deletes; "fixes" a failing row; reads the orchestrator's log to decide a row |

**Talking to the user:**
- Only the orchestrator talks to the user.
- The verifier's table is relayed as it came back, and never summarised into a pass that was not
  there.

**Why a separate verifier:** the agent that did the work is the worst judge of it. v1's lesson (06
§2.1) is that what was written down and checked held, and the rest did not.

---

## 3. Where progress is kept

Everything per machine is in `$HEP/.setup/`, which Heimdall's `.gitignore` leaves out:

| File | Holds | Written by |
|---|---|---|
| `state.toml` | each step's status and numbers; the machine; the choices; the gates; the deviations | the orchestrator only |
| `log.md` | one entry per event, newest last | the orchestrator only |
| `kept/` | the files kept before the wipe, copied in by P0 | P0 |
| `verify/<phase>/` | the verifier's scratch and its tables; P3's second work dir; P4's reference work dir | the verifier, P3, P4 |
| `stack.log`, `slow.log`, `compare_ref.py`, … | the long jobs' output; small scripts a step writes | the step that needs them |

`$HEP` is `~/Github/Heimdall` unless the user's start prompt names another place.

### 3.1 `state.toml`

```toml
# $HEP/.setup/state.toml — Heimdall's setup on this machine. Written only by the orchestrator (02 §3).

[machine]                       # P0.S1
host = "Lab_PC"
os = "Ubuntu 26.04 LTS"
arch = "x86_64"
cores = 24                      # logical CPUs
ram_gb = 31
disk_free_gb = 412              # where $HEP is
sudo = true
network = true
docker = "absent"               # "usable", "installed, no group", "absent"
apptainer = "absent"            # its version, or "absent"
python = "3.13.2"
annex = "ubuntu"                # targets/<annex>.md

[source]                        # P0.S2
repo = "/home/rajnoor/Github/Heimdall"
revision = "…"                  # git rev-parse HEAD when P0 ran
kept = "/media/…/kept"          # where the user's copies were

[choices]                       # the plan's defaults, or what the user said
packages = "@primary"
cores = 20
root_cores = 5

[step."P1.S2"]
status = "done"                 # todo | running | done | failed | blocked
started = 2026-10-20T09:12:00Z
finished = 2026-10-20T13:47:31Z
rows = { "R1" = 20, "R4" = 0 }  # each verification row's number or text
verified = "P1"                 # the phase whose verifier passed it (set at the phase's end)
note = ""

[[gate]]
step = "P1.S1"
asked = 2026-10-20T09:01:10Z
what = "sudo apt-get install: 51 packages, 1.2 GB"
answer = "yes"                  # the user's words, short

[[deviation]]
step = "P1.S1"
planned = "apt: libpcre3-dev"
did = "apt: libpcre2-dev (libpcre3-dev has no candidate on 26.04)"
allowed_by = "targets/ubuntu.md §allowed adjustments"
folded = ""                     # the Heimdall commit that put it into the plan files, once done
```

**Resuming:**
- Read `state.toml`, then take the first step that is not `done`.
- Re-run that step's **preconditions**. They decide whether its partial work is reusable: the
  stack's stamps (`$HEP/stack/.stamps/`) make P1 resumable on their own
  ([recipes/README.md](../../recipes/README.md) §1).
- A `running` step found on resume means the session died. Treat it as `failed`, collect what is
  there (§5.2), and run it again.

### 3.2 `log.md`

One line per event, plus at most a few lines of detail, so the whole story fits on a screen:

```
2026-10-20 09:01  P1.S1  GATE   sudo apt-get install (51 packages, 1.2 GB) — asked
2026-10-20 09:03  P1.S1  GATE   answered: yes
2026-10-20 09:12  P1.S2  START  build_stack.py packages=@primary cores=20 root_cores=5 (background)
2026-10-20 13:47  P1.S2  DONE   19 packages stamped
2026-10-20 13:55  P1     VERIFY 26/26 rows pass (verify/P1/table.md)
```

---

## 4. The step loop

The orchestrator repeats, until P4 is verified:

1. **Pick** the next step: the first `todo` (or `failed`) step whose phase's earlier steps are
   `done`. Phases run in order; within P1, nothing heavy runs beside the build (§8).
2. **Preconditions:** run them. One that fails means "not yet": report which, and either wait (a
   build still running) or go back to the step that should have made it true.
3. **Gates:** if the step's tasks touch a gate (§6), ask before the first such task and wait.
4. **Tasks:** do them as written, in order. Commands are copied, not paraphrased.
5. **Commit** only what a step says to commit (a deviation folded into these files, a fix to the
   template): stage by path, never `-a`. The message is `setup P<n>.S<m>: <what>`, with the
   attribution line the session is configured for. Top-Quark's first commit is `hep setup --git`'s.
6. **Verify:** run the step's rows (§5) and record each number in `state.toml`.
7. **Record** `done`, with a log line. Then go to 1.

At a phase's last step, the verifier runs the whole phase (§5.3). The phase report (§9) goes out
only after it.

---

## 5. Verification

### 5.1 A row

Every step ends with rows of this shape (the phase files use it):

| # | Command | Expected |
|---|---|---|
| R1 | `root-config --version` | `6.40.04` |
| R2 | `lhapdf list --installed \| wc -l` | `21` |
| R3 | `hep where --work` (from `~/Github/Top-Quark/configs`) | `/home/<user>/Github/Top-Quark`, exit 0 |

**The rules:**
- The **command** is exact and runs from a stated directory, with `load_hep` (`source
  $HEP/setup.sh`) done unless the row says otherwise.
- The **expected** value is a number, an exact text, or a stated tolerance (`σ within 3 % of
  12.4 nb`). "Works" or "looks right" is never expected.
- A row that cannot be run (a tool missing) is a **fail**, not a skip. Only a phase file may mark a
  row optional, and only with its reason.

### 5.2 A failing row

1. Collect: the command, its full output (to `verify/<phase>/` or the log), and the relevant log
   tails: `$HEP/forge/logs/<package>.log`, pytest's summary.
2. If the cause is plainly transient, run it once more: a network timeout, or a download the
   annex's caveats list (MadGraph and ONNX Runtime URLs, Geant4 data).
3. A row that fails twice is a **gate**: report the two outputs and the probable cause, propose the
   fix, and wait.
4. Never change the expected value, the command or the plan file to make a row pass. If the plan is
   wrong, that is a deviation (§7), asked for or allowed by an annex.

### 5.3 The verifier's pass

At a phase's end, the orchestrator starts the verifier with the prompt in §11.2 and the phase file's
name. The verifier:
- **runs** every row of every step of that phase, exactly as written, from a clean shell
  (`load_hep` only);
- **writes** to `verify/<phase>/` and to the scratch the rows name (the tests' `forge/scratch/`),
  and nowhere else;
- **returns** a table: `# · command · expected · got · pass/fail`;
- **adds** anything it noticed that no row covers, as a separate list;
- **changes** nothing.

**The phase is `verified`** when every row passes. Otherwise the failing rows go back through §5.2,
and the verifier runs again afterwards.

---

## 6. Gates

At a gate the orchestrator stops, asks in the form below, and waits. An approval covers that one
gate instance, never the next one of the same kind.

| Gate | Typically in |
|---|---|
| `sudo`, or any system package install or removal | P0, P1 (annex: system packages) |
| a download, with its list and total size (asked once per phase: the stack's tarballs; Geant4's ~4 GB of data) | P1 |
| a new recipe (`status = "new"`, MadAnalysis5 in `@primary`) that fails | P1 |
| a change to the user's account or groups (joining the docker group is the user's own action) | container annex |
| a deletion outside `$HEP/{stash,forge}` and `$HEP/.setup/verify` (V105); and `git clean -x` in Heimdall, never | any |
| a write to a High-Energy clone, if one is on the machine (it is left alone) | any |
| a change to the content of a work dir's `configs/` or `modules/` that the user made (Top-Quark's starter is `hep setup`'s) | any |
| `git push`, publishing a repo or an image anywhere | P4 |
| a verification row failing twice | any |
| anything the plan files do not decide, or decide in a way that cannot be done here | any |

**The form:**

```
GATE P1.S1 — sudo apt-get install: 51 packages, about 1.2 GB (the list: $HEP/.setup/apt.txt).
Why: the stack's system packages (recipes/settings.toml's apt_packages; targets/ubuntu.md).
If no: P1 cannot build; nothing else can proceed meanwhile.
Approve? yes / no / change …
```

---

## 7. Deviations

When the machine differs from what a plan says, the orchestrator may make a **deviation**, but only
when:
- an annex lists it as an **allowed adjustment** (for example, an apt package renamed on a newer
  Ubuntu); or
- it is a plain mistake in a plan's command (a wrong path, a typo) whose fix changes nothing else.

Everything else is a gate.

**Every deviation:**
- is recorded in `state.toml` (`[[deviation]]`) and in the log;
- is named in the phase report;
- is folded back into the plan files in `$HEP/docs/framework/` (or the recipe, when the recipe was
  wrong), by a commit at the end of its phase, so that the next machine does not hit it.

---

## 8. Concurrency and the machine

**The rules:**
- **One stack build at a time.** ROOT's compilers need about 3 GB each (`root_cores`).
- **One pytest session at a time.** The basetemp `forge/scratch/pytest` is wiped per session.
- **During the build**, the orchestrator keeps CPU-heavy work off the machine: no compiles and no
  tests. P2 needs the stack, so it waits for P1.
- **The slow suite (P2)** runs as the builder, in the background, after the fast suite passes.

**Cores and RAM:** P0 records them. P1 chooses `cores` and `root_cores` from them, by
[recipes/README.md](../../recipes/README.md)'s rules (one ROOT compiler per 3 GB). The choice is written to
`[choices]` before the build starts.

---

## 9. Reports

**At a phase's end**, after the verifier:

```
P1 done — verified 26/26 (verify/P1/table.md).
  ROOT 6.40.04 · Pythia 8.318 · Rivet 4.1.4 · YODA 2.1.4 · HepMC3 3.3.1 · FastJet 3.5.0 (patched) · MadAnalysis5 1.11.1 · 21 PDF sets
  deviations: 1 (libpcre3-dev → libpcre2-dev; annex-allowed; folded in a1b2c3d)
  took 4 h 35 min; 22 GB under $HEP
Next: P2.S1. No gate pending.
```

**At a gate:** §6's form. **When stopped** for any other reason: what was being done, what is known,
what is needed. Nothing else is said between reports, except to answer the user.

---

## 10. Rules carried over

Heimdall's `CLAUDE.md` holds them; in short:

- **Commits:** stage named paths, never `git commit -a`; never push without the gate.
- **Tests** write only their scratch (`forge/scratch/`). They never read or write a real work dir.
  The fixtures and `tests/reference/` are never regenerated.
- **Text files** are read and written with `encoding="utf-8"` (L17: reading a YODA file resets the
  locale).
- **Before touching a tool's code or folder**, read its rows in the knowledge ledger
  (`docs/07_Record.md` §3).
- **The user's files are the user's.** A work dir's `configs/` and `modules/` change only through
  listed, shown and approved diffs. High-Energy is not touched at all.
- **Never `git clean -x` in Heimdall:** it would delete `stack/`, hours of building. `forge/` and
  `stash/` may be emptied by hand.
- **The manual** stays generated where it is generated: after a schema `doc`/`notes`, `base.toml`
  comment or CLI help change, run `hep make --framework docs schema`.
- **Plans are not code.** An agent following these files changes code only as a step's tasks say.
  Ideas found on the way go to `bots/intent.md`, not into the code.

---

## 11. Prompts

### 11.1 Start (the user gives it to the first session)

```
You are the orchestrator for setting up Heimdall on this machine, following the plan files in
docs/framework/ of this repository (~/Github/Heimdall, which is $HEP).

Read, in order: docs/framework/README.md, 02_Agents.md. Then read $HEP/.setup/state.toml if it
exists.

Follow 02_Agents.md exactly: run the next step whose preconditions hold; stop at every gate of
02 §6 and ask me in its form; record every step in state.toml and log.md; have the verifier check
each phase before you report it done; never change a plan, a command or an expected value to make
a check pass — record a deviation (02 §7) or ask.

The files I kept before the reinstall are at: <path>.
Begin with P0 (03_Preflight.md), or resume where the state says.
```

### 11.2 The verifier (the orchestrator starts it at a phase's end)

```
You are the verifier for phase <P> of Heimdall's setup. You are read-only: do not edit, build,
install, commit or delete anything. You may write only to $HEP/.setup/verify/<P>/ and to the
scratch locations a row itself names.

Read $HEP/docs/framework/02_Agents.md §5 and the phase file <file>. Open a fresh shell,
run `source $HEP/setup.sh`, then run every verification row of every step of <P> exactly as written,
from the directory it states. Do not read $HEP/.setup/log.md or state.toml to decide a row.

Return a table: row · command · expected · got · pass/fail, and save it as
$HEP/.setup/verify/<P>/table.md. Then list anything you noticed that no row covers. Fix nothing.
```

### 11.3 Resume (any later session)

```
Resume Heimdall's setup as its orchestrator: read $HEP/docs/framework/README.md and
02_Agents.md, then $HEP/.setup/state.toml and the end of log.md, and continue by 02 §4.
```
