---
id: writing
summary: how a page is written, where a fact belongs, how anything cites anything
for: dev agent
---

# Writing

## Where a fact belongs

| The fact is | Its owner | Written by hand? |
|---|---|---|
| A setting's type, default, accepted values, effect | `framework/schema/`, `base.toml`, `recipes/settings.toml`, `tool.toml` | Only there; `reference/` is generated |
| A command's arguments | `cli.parser()`'s help | Only there; `reference/commands.md` is generated |
| How to get something done | one page in `stable/guide/` or `stable/setup/` | Yes |
| How it works inside | one page in `stable/internals/` | Yes |
| What a tool needs and what running it taught us | one page in `stable/tools/` | Yes |
| Why it is this way | a note in `stable/design/decisions/<area>.md` | Yes |
| What changed since the last crystallise | a live doc, `live/<slug>.md` | Yes |
| What must not happen | `rules/` | Yes, on the developer's word |
| What is still to do | `.plans/` | Yes |

**One fact, one owner.** Anywhere else, link. Prose never states a default, a list of accepted values or a command's flags: it links to the reference, because those are what drift first.

## A page

```
---
id: identity
summary: one line, enough to decide whether to open the page
for: dev agent
code: framework/runner/record.py, framework/runner/tools.py
---
```

- `id` is unique and outlives moves: code cites `doc:identity`, never a path and section.
- `for` names its readers: `driver` (uses Heimdall on a project), `mechanic` (sets it up), `dev`, `client` (an AI in a work dir), `agent` (an AI developing Heimdall).
- `code` names the files the page describes; `heimdall docs --drift` watches them, and a test checks they exist.
- One subject a page, at most 12 KB. A page that outgrows that is two subjects.
- Open with what the reader gets, not with history. Say what holds, not how it came to.

## A decision note

A bullet of at most 300 characters: the id in bold, what was decided, `Gave up:` what it cost, `Superseded by` a later id. The full account of an old note is in git, at tag `docs/pre-rebuild`. Ids are never reused.

## Style

- Plain words, short sentences, the exact name of the thing in a code span.
- Dense, not terse: drop filler, keep the reasoning a reader needs.
- `for: driver` and `for: mechanic` pages carry no record ids and no dates.
- A diagram or table when it says it better than prose, and not otherwise.

## Citing

- **Code to docs:** `doc:<page id>`.
- **Code to a reason:** a note's id (`# L17`), only where the line would look wrong without its reason. Not on every line a decision touched.
- **User-facing strings** (help, hints, errors) cite no record id. They name a command, or a page's path.
- **Docs to docs:** a relative link. A test resolves it.
