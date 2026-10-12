# Heimdall on a fresh machine: the plan set

These files are what an agent (or a person) follows to set Heimdall up on a fresh machine, starting
from a clone of this repository:
- the stack, built from source into Heimdall itself (`@primary`: the lab PC's set plus
  MadAnalysis5);
- the framework built and tested against it;
- a first work dir, **Top-Quark**, made by `hep setup` and run;
- the physics checked against the lab PC's numbers, then the handover.

The first machine is the lab PC, reinstalled. The same files serve the next machines; the annexes
in `targets/` hold what differs between them.

**What is already done, and is not a step here.** Heimdall was seeded from High-Energy at
`split/base` (5e0a913), and the seam was made and tested on the old lab PC against its stack:
- two roots, `hep setup`, `hep where`, the build split, provenance across both repositories, the
  tests on the fixture work dir, the macOS spots, and the manual re-rooted (V105–V113 in
  [07](../07_Record.md#2-decisions));
- the recipes moved into `recipes/`, with the toolkits (V109–V110).

The plans that did that, rounds 1–2c (the couplings C1–C80, the move map, the seed and the seam
phases), are in Heimdall's history (`git show c6e7590:docs/framework/04_Seed.md`, `…/06_Seam.md`) and
in High-Energy's (`git show split/base:docs/framework/…`). [01_Target.md](01_Target.md) is kept: it is
the design the code cites by section (`framework/01 §5.2`).

---

## 1. The phases

| Phase | File | Does | Background | Gates expected |
|---|---|---|---|---|
| P0 | [03_Preflight.md](03_Preflight.md) | survey the machine and choose the annex; clone Heimdall; `.setup/`; bring back what was kept | — | sudo, if `git`, `curl` or `python3-venv` are missing |
| P1 | [04_Stack.md](04_Stack.md) | the system packages; `recipes/build_stack.py packages=@primary` into the machine root (`~/Himinbjorg`: `stack/ forge/ venv/`); the stack's checks | the build (hours) | sudo/apt, downloads, a new recipe (MadAnalysis5) that fails |
| P2 | [05_Framework.md](05_Framework.md) | `hep build --framework`; the C++ tests and the fast suite; the slow suite and its physics gates; the manual's checks | the slow suite | a gate row that differs twice |
| P3 | [06_Workdirs.md](06_Workdirs.md) | Top-Quark made by `hep setup --project Starter --git`, built, checked and run; a throwaway second work dir, and independence | — | none |
| P4 | [07_Verify.md](07_Verify.md) | the reference point on its seed against the lab PC's kept products; the handover: report, memory, publishing | — | push / publish |

[02_Agents.md](02_Agents.md) is how the agents run them: the roles, the state in `$HEP/.setup/`, the step
loop, verification, gates, deviations and reports. **A fresh machine starts at 02 §1.**

---

## 2. The target

```
~/Github/Heimdall/                  = $HEP: the framework, what git has (V105, V122)
  README.md CLAUDE.md .gitignore Makefile pytest.ini setup.sh (load_hep)
  recipes/                          build_stack.py toolkits/ settings.toml patches/ platforms/
  env/                              hep_env.sh flags.sh stack.toml stack.py
  framework/                        bin/ runner/ tools/ schema/ templates/work/ rules.mk work.mk hepkit.py
  src/                              the kits (*.hh), App_*.cc, Apps/Paint/
  docs/  bots/  tests/
  .setup/                           (ignored) the agents' state
~/Himinbjorg/  ($HEP_MACHINE)      outside git: stack/ venv/ apps/ forge/ stacks/ machine.toml machine.sh

~/Github/Top-Quark/                 a work dir, made by `hep setup` (V107); others anywhere
  hep.toml Makefile .gitignore README.md CLAUDE.md .vscode/
  configs/Starter/  modules/Starter/  datasets/ results/ output/ reports/ build/
```

Every folder and file is in the manual, [06 §1](../06_Internals.md#1-layout-heimdall-and-work-dirs).
High-Energy is not needed on the new machine: the tests carry their own work dir, and the reference
point (P4) runs from it. It stays the user's, untouched; turning it into a work dir is parked
([06_Workdirs.md](06_Workdirs.md), appendix).

---

## 3. The decisions in force

The user's, through round 2c (2026-10-08 to 10-10), as built. Each is a V-row of the record now.

| # | Decision | V |
|---|---|---|
| D26 | Heimdall is `~/Github/Heimdall`, and it **is** `$HEP`: the recipes, the environment, the framework, the kits and, ignored, the stack and its builds | V105 |
| D27 | in the machine root: `forge/` downloads, sources, builds in progress and logs; `stack/` installs; `venv/`; `apps/` the ready apps | V105, V109, V122 |
| D3, D4 | a work dir is marked by `hep.toml` (`[work]`), found by walking up; work dirs are independent and share only Heimdall | V106 |
| D14 | `hep setup <dir>` makes a work dir, never overwriting | V107 |
| D8 | provenance records both repositories' revisions | V111 |
| D9 | the tests run in a frozen fixture work dir, synced into `$HEP_FORGE/scratch/` | V112 |
| D11 | one framework for every target; portability is framework code | V113 |
| D12 | three agents: orchestrator, builder, verifier (02) | — |
| D31 | High-Energy is left alone | — |
| D32 | Top-Quark is made fresh by `hep setup --project Starter --git`, as the test work dir | — |
| D33 | never `git clean -x` in Heimdall: it would delete the stack | V105 |
| — | `@primary` is the stack a fresh machine gets: the lab set (`packages=all`) plus MadAnalysis5 (the user, 2026-10-10) | V110 |

---

## 4. Step format

Each phase has 2–3 steps. Each step gives:
- its id and goal;
- **preconditions:** the earlier steps done, plus probe commands;
- **tasks:** exact commands;
- the **gates** it touches;
- **verification rows:** a command and the number or text it must give;
- **on failure:** what to collect, and when to stop.

**Logs are per machine,** in `$HEP/.setup/log.md`, never in these files. A deviation (02 §7) is
folded back into these files by a commit, so the next machine does not meet it.
