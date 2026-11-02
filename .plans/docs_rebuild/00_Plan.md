# Docs rebuild: one knowledge base, five doors

Status: design, decisions taken 2026-11-02. On approval this file moves to `.plans/docs_rebuild/00_Plan.md` (plan mode only allows
writing here; the repo's rule is `.plans/`).

## Context

Measured on 2026-11-02 at `9e895c8`:

| Finding | Evidence | What it forces |
|---|---|---|
| Too big to read | `docs/` 1.17 MB (~300k tokens), `.plans/` 301 KB; 07_Record alone 312 KB | Agents cannot load it; a dense entry point and small pages are needed |
| Old words survive | in `docs/`, READMEs: `hep ` 294 lines, `utils/` 99, `[run]` 69, `hep.toml` 42, `$HEP` 40, `bots/` 28; the glossary still says `$HEP`, `hep setup`, `[run]` | Nothing detects drift in prose; carried claims must be re-verified against code, not copied |
| One concept, many pages | "identity" appears on all 8 pages; 04 §, 02 §, 06 § each explain parts of it | One owner per fact, enforced |
| Decisions rot in place | 246 record rows, median 944 chars, max 4,250; chronological, so V1 still reads `utils/Env/run` | Rows short, grouped by subject, superseded rows marked |
| Code is coupled to the record | ~2,400 id cites in code (V 1,963 of them; schema notes 643), ~360 `docs/… §n` cites; 80 appear in strings at runtime; 76 V rows cited by no code; dead cites exist (`BOT.md`, `rework_v2`, `docs/framework/06_Seam.md`) | Page moves must not break code again: cite stable ids |
| Settings are already data | schema 159 keys, 0 undocumented; `heimdall explain`, editor JSON schema, 04's tables all derive from it. But `src/Apps/Paint/base.toml` and `recipes/settings.toml` are separate sources, and v3 prose sits in Python (`docs.py` `V3_DOCS`) | The user's door is mostly generation work, not writing |
| CLAUDE.md is state | Layout table, plan filenames, test variables | Split into behaviour (AGENTS.md) and repo rules (docs/rules) |
| Work-dir agent context is thin | template `CLAUDE.md` says "read the manual" (500 KB) | A generated, budgeted context |

Plan for it: new tree first, old tree deleted last (expand → migrate → contract). Everything old stays reachable at a local
tag `docs/pre-rebuild`.

## Design

### Principles

1. **Knowledge is organised by subject, not reader.** Readers get doors (views) onto one body; no per-audience copies.
2. **One fact, one owner.** A code-derived fact is owned by code and never restated by hand. Prose never states a default,
   a choice list or a command's flags: it links to the reference.
3. **Precedence on conflict: code > generated reference > live > stable > plans.** A reader who finds a conflict reports it.
4. **Stable ids, not locations.** Code cites `doc:<page-id>`, and decision ids; never a file path with a section number.
5. **Checks instead of promises.** Anything a test can hold, a test holds.

### Layout

```
AGENTS.md                    behaviour only (below); CLAUDE.md is `@AGENTS.md` + `@docs/rules/invariants.md`
README.md                    the project's front door, short
docs/
  README.md                  the four doors; how the docs work
  MAP.md                     GENERATED agents' index: each page's id, summary, readers, size, live overlays
  rules/                     binding now, changed on the developer's word, no crystallise cycle
    invariants.md            what must never happen here and why (machine root, identities, git, downloads, tests)
    writing.md               page format, owner rule, style, budgets, citing
    work.md                  .plans shape; live-doc format; the crystallise protocol
  reference/                 GENERATED, always current, never hand-edited, not subject to crystallising
    settings/  errand.md  plot.md  style.md  tools.md  report.md  cluster.md  stack.md (the mechanic's)
    commands.md              every command, from argparse
    keys.md                  compact: key | type | default, one line each (agents grep this)
    legacy.md                v2 → v3 names, from the v3 table
  client/CONTEXT.md          GENERATED, ≤ 16 KB: primer + command names + pointers; `heimdall context` prints it
  stable/                    crystallised, authored
    CRYSTAL.toml             the commit the stable tree was last reconciled against
    start/                   model (the primer), first run
    setup/                   the mechanic's: fresh machine, stack and recipes, toolkits, conda base, platforms, images, cluster
    guide/                   errand file, sweeps, chains, your programs, scale, watching & reruns, failures,
                             housekeeping, results from Python, plots (stage, figures, data & ratios, style, reports)
    tools/<tool>.md          one per tool folder: use, and its knowledge-ledger rows (L…)
    internals/               layout, ranks, data model, a run in code, connections, identity & seeds, records & caches,
                             events, failures, plot stage, Paint, build, stack, tool contract, C++ kits, tests
    design/                  principles, what is refused, glossary, decisions/<area>.md
  live/
    README.md                the format, in two lines; never deleted
    <slug>.md                what changed since the last crystallise
.plans/
  ISSUES.md                  pending work; each issue ≤ ~10 lines, links to a plan if it has one
  plans/<slug>/              a plan in progress; deleted when done (git keeps it)
  audits/<slug>.md           an audit with findings still open
```

**Page format.** Flat frontmatter that GitHub renders as a table, parsed by a few stdlib lines:

```
---
id: identity
summary: what a point's identity hashes, how seeds derive from it, what changes it
for: dev agent driver
code: framework/runner/record.py, framework/runner/tools.py
---
```

Soft cap 12 KB a page, so an agent reads one fact's page, not a chapter.

### The five doors

Two kinds of human user (the developer's distinction): the **mechanic** sets Heimdall up and keeps it running; the **driver** uses it on a project.

| Reader | Door | How it is served |
|---|---|---|
| **Driver** (a setting: effect, accepted values) | `heimdall explain <key>`, editor hover, `docs/reference/settings/`, `heimdall docs` (a searchable settings tree), `stable/guide/` | One source, the schema; extended to style settings and table listing (`explain plot`) |
| **Mechanic** (install, stack, toolkits, platforms) | `stable/setup/`, `reference/settings/stack.md`, `explain` for stack settings | `recipes/settings.toml` as the source; absorbs `recipes/README.md`, the Mac README, `docs/framework/`, `docs/conda/` |
| **Dev** | `docs/README.md` → `stable/internals`, `design/`; `heimdall docs` node tree of pages | Same pages as Agent |
| **Client AI** (in a work dir) | `heimdall context`, then `heimdall explain`, `heimdall check` | Version-matched and works without knowing paths; template CLAUDE.md points to it |
| **Agent** (developing Heimdall) | `AGENTS.md` → `docs/rules/` → `docs/MAP.md` → the one page; `reference/keys.md` by grep; ids by grep | Pages are dense; no second copy |

**The primer is owned once:** `stable/start/model.md` owns the model, vocabulary and file tree; `client/CONTEXT.md` is
assembled from it, so the digest cannot contradict it.

**Tools beyond markdown, deliberately few (stdlib only):**
- `heimdall docs`: builds one self-contained HTML into `$HEIMDALL_MACHINE/forge/docs/` (`~/Himinbjorg/forge/docs/`: disposable, not live state) and opens it: settings tree with
  search, page tree filterable by reader with summaries and links, and a graph of page ↔ code ↔ decision. Not committed (Heimdall holds "what is
  authored, nothing built").
- `heimdall make --framework docs schema`: regenerates reference, MAP and CONTEXT (existing command, wider).
- `heimdall docs --drift`: pages whose `code:` paths changed since `CRYSTAL.toml`'s commit and that no live doc names. This is
  the drift detector prose has never had.
- Generated markdown **is** committed: agents and GitHub need it without a stack; a test fails when stale (as today).

Rejected: MkDocs/Sphinx (dependency, restates nothing we need); embedding search/RAG/MCP (grep plus a map is cheaper and
cannot be stale); a graph database; one ADR file per decision (234 files); per-audience page copies (the duplication we are
removing); committed HTML (churn, against "nothing built").

### Decisions and ledger (the footnotes)

A label such as `# L17` in code is a footnote to one note explaining why. Chosen by the developer: labels stay and keep resolving; notes shrink. New code adds a label only where a line would look wrong without its reason; existing comments are not swept. Labels leave schema notes and runtime strings. `I-`/`U-` labels are removed, as their rows are deleted.

Rows move from one chronological table to `stable/design/decisions/<area>.md`, by subject. Each row:
`**V96** {var:…} replaced after imports, so identity sees only the result. Gave up: … . Superseded by V…` (≤ 300 chars).
The full account stays in `git show docs/pre-rebuild:docs/07_Record.md`. Tool ledger rows (L) go into `tools/<tool>.md`,
others into their internals page. Verified-section and budget tables, the brief and v1's findings are not carried unless
code cites them; a test requires every id cited in code to resolve (grep finds it in one hop).

### Live and crystallise

- **Live doc:** `docs/live/<slug>.md`, one per feature or change, frontmatter `affects: <page ids>`, `issue`, then only: what
  now holds, what no longer does, new decisions (with their V ids), and what stable pages need. State, not steps. Written in
  the same commit as the code, or at the phase commit. Facts owned by code go in code, not here.
- **Reading:** MAP.md shows each stable page's live overlays; a page's overlay wins until crystallised.
- **Crystallise, only on the developer's explicit order:** (1) `heimdall docs --drift` and read all live docs; (2) per claim,
  verify against code, merge into the owning page, rewriting rather than appending; (3) decisions into their area files;
  (4) empty `live/` except its README; (5) set `CRYSTAL.toml`; (6) tests green, one commit, report what merged, what was
  dropped and why.

### AGENTS.md (draft, behaviour only)

Holds no paths beyond the docs entry, no features, no state; a test caps its size and refuses repo paths other than `docs/`.

```markdown
# How to work here
Read docs/rules/ first, then docs/MAP.md, then only the pages your task needs. Do not read whole trees.

## Truth
- Code beats docs; generated beats written; live beats stable. Docs are claims: verify one before building on it.
- A contradiction is a finding: report it, and fix it if it is in scope. Never quietly pick a side.
- Say what you checked and how. "Done" means verified; a failure is reported with its output.

## Planning
- Non-trivial work gets a plan file in .plans/ before any code, written progressively, linked from its issue.
- Read the code before proposing. Treat inherited plans and issues as claims to re-verify.
- Ask every decision up front, batched, each with a recommendation. Nothing is asked mid-execution that could have been
  asked before.
- Implement only on the developer's explicit order. Planning approval is not an order to build.

## Execution
- Follow the plan's order; verify each phase by its named check before the next.
- One concern per commit, staged by path. Never push without being asked.
- Stop at the plan's marked milestones; write the state reached where the next session reads it.
- Before anything hard to reverse, outward-facing or costly: look, then ask.
- If what you learn invalidates a decision, bring it back as a question with evidence.

## Documenting
- One fact, one owner. Link rather than restate. Never hand-write what is generated; change its source and regenerate.
- With each change that alters what a reader may rely on, write or update its live doc in the same commit.
- Never edit stable docs or crystallise unless ordered.
- Finished work leaves .plans/: the issue is deleted, the plan deleted, decisions kept.

## Memory
Keep preferences and how the developer wants work done. Never repo facts: those go in docs, or they rot in two places.
```

## Phases

Size XL overall; pause at the phases marked ⏸. Test command throughout, stack loaded:
`taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_docs.py`

| # | Phase | Verified when | Blocked by |
|---|---|---|---|
| 0 | Local tag `docs/pre-rebuild`; `.plans/docs_rebuild/` with this plan and **salvage map**: every old file and section → destination or wipe, with reason; old-section → `doc:<id>` table | Every heading in old `docs/`, `.plans/`, covered by a script | — |
| 1 | **Pilot ⏸**: `docs/rules/*`, frontmatter, generator for MAP and `reference/settings/plot.md`, `heimdall docs` tree, one guide page (plots), one internals page (identity), one area of decisions, one live doc, a dry crystallise | You read them and judge the feel; new tests pass beside the old | 0 |
| 2 | Reference complete: move `V3_TABLES`/`V3_DOCS` to `framework/schema/v3.toml`; strip record ids from schema notes; settings for style and stack; `explain` covers them and lists tables | Every key, style key, stack setting, tool option in `reference/`; `explain` answers each | 1 |
| 3 | `stable/design` and `stable/internals`, each claim verified against code; notes distilled | Every cited V/L/F/R/C id resolves; page caps hold | 1 |
| 4a | Driver: `stable/start`, `guide`, `tools` | All TOML examples load; every tool has a page; no study names | 2, 3 |
| 4b | Mechanic: `stable/setup` from `recipes/README.md`, the Mac README, `docs/framework/`, `docs/conda/`; those READMEs become 3-line pointers | Every toolkit, platform and stack setting reachable; no study names | 2, 3 |
| 5 | `CONTEXT.md`, `heimdall context`, template `CLAUDE.md`/`README.md`, `heimdall docs --drift` | **Cold test:** a fresh agent given only `heimdall context` in a scratch work dir writes an errand file `heimdall check` accepts | 4 |
| 6 | `.plans/` rebuilt: open issues re-verified against code; audit 2 and 4's open findings, handoff's three next pieces become issues; finished plans wiped | Each kept issue names its check; nothing marked open is already done | 0 |
| 7 | **Contract ⏸**: code cites → `doc:<id>` by the table; runtime strings cite no record ids; issue and audit ids out of code; dead cites fixed; `AGENTS.md`/`CLAUDE.md`; `test_docs.py` rewritten; old files deleted; memory reduced to preferences | Full fast suite green, gates untouched; `docs/` holds no old page; **cold test 2:** a fresh agent given only AGENTS.md finds where identity is computed and why in ≤ 3 reads | 3, 4, 5, 6 |

`test_docs.py` afterwards holds: links; TOML examples; every key documented; generated current; frontmatter valid; ids unique;
`code:` paths exist; every `doc:` and decision id cited in code resolves; size caps (page, CONTEXT, decision row); `for: user`
pages cite no record ids; AGENTS.md carries no repo paths; live docs' `affects` resolve; rank table.

## Decision log

| Decision | Chosen | Why |
|---|---|---|
| Organise by | subject, with doors | Audience copies are the source of contradiction |
| Generated markdown | committed, tested | Readable without a stack |
| HTML | built on demand, into machine root | "Nothing built" in Heimdall |
| Stable pages' format | markdown + flat frontmatter | Stdlib, renders on GitHub, greppable |
| Rewrite vs move | rewrite, verifying against code | Hundreds of stale lines measured |
| Footnote labels | keep, short notes, cite sparingly (developer) | Keeps 2,400 line-to-reason links without carrying 270 KB |
| Recipes docs | included (developer) | One owner for the stack; creates the mechanic door |
| New commands | `context`, wider `explain`, `docs` + drift, HTML in `~/Himinbjorg/forge/docs/` (developer) | Serves driver, client AI and drift detection |
| Writer | Claude alone, in sequence, no subagents (developer) | One voice; expect several context compactions, so each phase writes its state to `.plans/docs_rebuild/` |

## Not yet specified

- Phase 1's pilot may adjust page caps and the tree's look; a change to the layout comes back to you at the ⏸.
- Exact page list in `internals/` and `guide/`: fixed by the salvage map in phase 0.

## Assumptions (correct any on this plan)

1. `AGENTS.md` is canonical and `CLAUDE.md` imports it, because Codex and Copilot have been used here (`.codex/`, `.plans/Copilot_*`).
2. Repo-specific hard rules (git, machine root, identities, tests) are repo rules, so they go to `docs/rules/invariants.md`, not AGENTS.md; `CLAUDE.md` auto-loads them, and AGENTS.md tells other agents to read them first.
3. `.plans/` keeps only what is open: restructure_plan's open milestones become issues; finished plans are wiped.
4. `editor/`'s README, `tests/fixtures/`' READMEs and `tests/reference/` are out of scope.
5. Code comments citing `docs/… §n` are all rewritten to `doc:<id>` in phase 7, in one mechanical commit.
6. New decisions keep the V sequence; between crystallisings a new note sits in its live doc and the id test accepts it there.
7. Each phase is its own commit; nothing is pushed.

## Always / Never

- Always: old tree intact until phase 7; commits by path; `tests/reference/` and fixtures untouched; schema `doc`/`notes` text
  changes regenerate.
- Never: push; touch `~/Himinbjorg`'s live files; touch a work dir; rebuild an app or plugin; change runtime behaviour other
  than the new read-only commands and hint wording; name a real study.

## Progress

| Phase | Status |
|---|---|
| Design | in review |
