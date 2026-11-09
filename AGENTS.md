# How to work here

Read docs/rules/invariants.md first. Read docs/rules/code.md before writing code, docs/rules/writing.md before writing docs, docs/rules/work.md before planning or recording work. Find a page by searching docs/MAP.md for your subject, then read only that page. Do not read whole trees, or the whole map.

## Truth

- Code beats docs; generated beats written; live beats stable. Docs are claims: verify one before building on it.
- A contradiction is a finding: report it, and fix it if it is in scope. Never quietly pick a side.
- Say what you checked and how. "Done" means verified; a failure is reported with its output.

## Planning

- Work moves through the pipeline in docs/rules/work.md: source (audit or spec) → design plan for the developer → implementation round for an agent → review by another session → close into .plans/Issues.md and .plans/Notes.md. Say which stage you are in, and do only that stage's work.
- Non-trivial work gets a plan file in .plans/ before any code, written progressively, linked from its issue.
- Read the code before proposing. Treat inherited plans and issues as claims to re-verify.
- Ask every decision up front, batched, each with a recommendation. Nothing is asked mid-execution that could have been asked before.
- Implement only on the developer's explicit order. Planning is not an order to build.

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
