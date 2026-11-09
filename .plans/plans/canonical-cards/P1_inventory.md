# P1 Inventory: what the real cards hold

**Verified when:** `notes/inventory.md` lists, per tool folder, every base card the fixtures and the real work dirs use, and, per card: its settings count, each duplicate key (lines, values), each order-sensitive key (Pythia `Tune:*`, particle-data commands, Herwig `cd`, Delphes blocks), and each comment directive. The developer has read it ⏸. Nothing is written but the note.

### 1.1 The probe (S)
- Acceptance: a scratch script (not in the repo) parses each base card with today's `tools.card_parser` and `tools._cleaned`, and Sherpa's with a YAML loader that records duplicate keys. Read-only on the work dirs.
- Check: `python3 <scratch>/inventory.py ~/Github/Heimdall/tests/fixtures/work <work dir 1> <work dir 2> > notes/inventory.md`
- Files: `notes/inventory.md` (new).
- Seam: none (a report).
- Blocked by: the gate.

### 1.2 The rules each folder needs (S)
- Acceptance: a table in the note maps each finding to a `[card]` rule (`order`, `duplicates`, `leading`, `repeatable`, `directives`), or to a question for the developer when no rule fits.
- Check: the table covers every finding of 1.1.
- Blocked by: 1.1.

## Log

- 2026-11-09: 1.1 and 1.2 done. The probe is kept as `notes/inventory_probe.py`, since P5 reuses its walk over the snapshots. Findings 1–7 and the rules table are in [notes/inventory.md](notes/inventory.md). Finding 3 refines the `free` writer (P2 2.3). ⏸ Question A (the duplicated `HeavyIon:SigFitNGen`) is open for the developer.
