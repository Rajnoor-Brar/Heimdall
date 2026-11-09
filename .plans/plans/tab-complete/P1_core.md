# Phase 1: commands and options

Plan: [00_Plan](00_Plan.md). Blocked by: none (decisions in hand 2026-11-09). Size: S.

## Steps

1. **`complete.py`, the walk (S).** `words(cword, argv) -> (candidates, directive)`. From `cli.parser()`:
   - the top-level options (`--plain`) and the command names;
   - then the command's subparser: its options not given yet, and an option's `choices` when the word before is that option;
   - a positional's `choices` (`records`, `library`, `image`).

   The retired stubs (`stats`, `deck`) are left out.
2. **The hook (XS).** `cli.main`: `if argv[:1] == ["__complete"]`, before `parse`. It prints the candidates and the directive line and returns 0. Any `HeimdallError` or `OSError` prints nothing and returns 0.

## Checks

- `tests/runner/test_complete.py`:
  - `run --q` gives `--queued-to`;
  - `records ` gives `upgrade`;
  - `--plain r` gives `records`, `recognise`, `report`, `reproduce`, `run`, `runs`;
  - the stubs are absent.
- **Nothing written:** the scratch work dir's tree and the registry's mtimes are the same before and after.
- **Time:** 20 completions in a row, the slowest under 150 ms (a subprocess, as bash calls it).

## Log
