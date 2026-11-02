---
id: history
summary: where Heimdall came from, in a dozen lines
---

# History

| | |
|---|---|
| **v0** | a hand-built `utils/` (10,404 lines of C++) and four scripts around Pythia → FIFO → `rivet` |
| **v1** (tag `rework/v1-final`, in High-Energy) | a Python orchestrator (17k lines, 19 commands) over one in-process C++ event loop (6.8k lines), CMake, 33k lines of tests |
| **v2** (2026-09-26) | the developer's design: tools as processes, one errand file. v1's code was deleted and its knowledge kept |
| **audit 1** (V52–V79) | the schema, frozen fixtures, tool folders as data, LaTeX labels, the event stream, the mpl backend, `check`, `migrate`, `reproduce` |
| **figures** (V80–V89) | `[plot.figures]` |
| **Heimdall** (V105–V113) | split from High-Energy into its own repository |
| **audit 3** (V116–V136) | the machine root, toolkits as files, the third errand form, `records/`, one command line |
| **conda** (V140–V155) | a conda base by default, `heimdall`, `gjallarhorn`, `bifrost`, images |
| **task H** (V156–V160) | snapshots, records as configs, statistics |
| **run logging** (V195–V205) | attempts, digests, `run.jsonl` |
| **reports** (V206–V218) | `heimdall report`, replacing decks |
| **names** (V213, V225–V229) | `hep` → `heimdall`; Assignment, Errand, Run |
| **docs rebuild** (2026-11) | this manual. The old one is at tag `docs/pre-rebuild` |
