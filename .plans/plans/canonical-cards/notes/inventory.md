# P1 inventory: what the real base cards hold

Made on 2026-11-09 by [inventory_probe.py](inventory_probe.py), read-only, with each folder's own grammar (`tools.card_parser`, `tools._cleaned`), and Sherpa's with a YAML loader that records duplicate keys. It read:
- the test fixtures' `configs/`;
- two real work dirs' `configs/`;
- every distinct copy a Run snapshot keeps (`records/<A>/<E>/<R>/config/`) that differs from `configs/`.

The real work dirs are called work dir 1 and work dir 2, and their cards are numbered.

Rerun it with:

```bash
python3 notes/inventory_probe.py <work dir>...
```

## Counts

| | pythia | sherpa | herwig | delphes | whizard | madgraph |
|---|---|---|---|---|---|---|
| fixtures | 5 | 2 | 2 | 1 | 1 | 1 |
| work dir 1 (configs + distinct snapshot copies) | 12 + 4 | 9 + 23 | 1 | 1 | 1 | 1 |
| work dir 2 (no records) | 2 | 1 | 1 | 0 | 0 | 0 |

Work dir 1's Runs ran with 27 versions of its base cards that are no longer in `configs/` (4 Pythia, 23 Sherpa). So P5's proof must plan each Run from its own snapshot, never from `configs/`.

## Findings

1. **A Pythia key twice in one card.** The fixture `configs/Decay/decay.cmnd` and work dir 2's copy of it both hold `HeavyIon:SigFitNGen = 200` at line 35 and `HeavyIon:SigFitNGen = 0` at line 38. Today the last line wins, so the runs use **0**, with `HeavyIon:SigFitDefPar = 1.67,20.13,0.14`. But the card's comments say the 200 is wanted ("let Glauber fit Ne-20 geometry"), and that the `SigFitDefPar` values "were Pb params" and should go. So the card runs the opposite of what its comments intend. Under gate Q1 this card is refused at its next plan. Work dir 2 has no records, so nothing needs remaking there. *Question A below.*
2. **Tunes.** Only `Tune:pp` appears, in the same two cards, at line 26. It comes after nine settings: `SoftQCD:nonDiffractive` and particle data for 1000100200, 3122, 310, 3312, 3322 and 3334. A tune sets no particle data and no process switches, so putting it first changes nothing in these cards. No card has `Tune:ee`.
   - *Assumption:* once tunes lead, a setting the tune would reset wins, wherever it was written. Today it is lost when written above the tune.
3. **Particle data.** Particle 3122 has `mayDecay`, `onMode = off` and then `onIfMatch`. `onMode` and `mayDecay` are not in `repeatable`, but their order against `onIfMatch` is meaning: `onMode = off` written after an `onIfMatch` would close the channel again. So the `free` writer keeps **every** `<id>:` command of one particle together, in written order, whether repeatable or not (gate Q6). The base's commands come before the point's, as the run reads them today. *Plan change: P2 2.3 and Design step 4 now say this.*
4. **Sherpa.** No card has a duplicate key. Every card has lists whose order is meaning (`PDF_SET`, `PROCESSES`, `SELECTORS`, `ME_GENERATORS`, `BEAM_*`, `SCALE_VARIATIONS`), so they stay in order.
   - One snapshot copy in work dir 1 starts with `gjallarhorBEAM_POLARIZATIONS: [0.0, 0.0]`: a stray paste into the card. Sherpa read it as an unknown key and left `BEAM_POLARIZATIONS` at its default, which is also `[0, 0]`. The physics is the same. The remake plans that snapshot as recorded and keeps the stray key.
5. **Delphes.** The ATLAS card repeats `InputArray`, `OutputArray`, `EfficiencyFormula`, `PTMin` and 25 other keys, each inside a different `module { … }` block (33 blocks). These are block-scoped, not duplicates. Delphes stays `sequential`, and Q1's refusal applies to `free` folders only.
6. **Herwig.** Both bases `cd` (`cd /Herwig/Generators`, `cd /Herwig/MatrixElements/`) and then `insert` relative to it. So Herwig is `sequential`.
7. **Whizard, MadGraph.**
   - Whizard has one directive, `# heimdall: beam_structure = pdf_builtin, epa` (line 55), and its commands (`alias`, `process`, `integrate`, `simulate`) run in order.
   - MadGraph's proc card is `import` and then `generate`.
   - Both are `sequential`. No other folder's comments carry a directive.

## The rules each folder needs (1.2)

| Folder | `order` | A free key twice in one card | `leading` | Kept in written order | `directives` |
|---|---|---|---|---|---|
| pythia | `free` | refused (Q1); see question A | `Tune:ee`, `Tune:pp` | each particle's `<id>:` commands, base then point | none |
| sherpa | `tree` | refused; none exist | — | lists | none |
| herwig | `sequential` | not applied (scripts) | — | the base, as written; the runner's `set` lines sorted | none |
| delphes | `sequential` | not applied (block-scoped) | — | the base, as written; the runner's `set` lines sorted | none |
| whizard | `sequential` | not applied | — | the base, as written | `^#\s*heimdall:\s*(\w+)\s*=\s*(.*)$` |
| madgraph | `sequential` | not applied | — | the proc card, as written | none |

## Question for the developer (P1 ⏸)

**A. The duplicated `HeavyIon:SigFitNGen`.** Gate Q1 refuses this card. Which line goes?
- **Recommended:** you pick by physics, since the card's comments and its behaviour disagree.
  - Keeping today's physics means deleting line 35 (`= 200`).
  - Following the comments means deleting line 38 (`= 0`) and the Pb `SigFitDefPar`.
- The fixture changes the same way, together with P3's refusal test. Work dir 2's card is yours to edit, or mine on your yes.

**Answer A (the developer, 2026-11-09): "Use 200".** Line 38 (`HeavyIon:SigFitNGen = 0`) goes from the fixture, in P3 with its refusal test. `SigFitDefPar` stays, since the answer named only `SigFitNGen`; with the fit on, Angantyr uses it as the fit's starting values. Work dir 2's card is left alone for now: "update work dir 2" (back up, then the same edit) is a later task (P5 5.3).
