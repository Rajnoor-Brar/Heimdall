# Phase 3: the bash function

Plan: [00_Plan](00_Plan.md). Blocked by: phase 2. Size: S.

## Steps

1. **`env/complete.bash` (S).** `_heimdall`:
   - `heimdall cd`, `refresh` and `quit` are answered in bash, since they are the shell function's own;
   - everything else goes to `command heimdall __complete "$COMP_CWORD" "${COMP_WORDS[@]:1}"`, with the directive line read.

   `complete -F _heimdall heimdall`.
2. **Wiring (XS).**
   - `heimdall_env.sh` sources it beside the functions, before the early return at `:217`, so a child shell gets it too.
   - `quit` runs `complete -r heimdall`.
   - Check `compopt` (bash ≥ 4). Without it, there is no `nospace`.

## Checks

- `tests/runner/test_complete.py`: `bash --noprofile --norc -c` sources `env/complete.bash`, sets `COMP_WORDS` and `COMP_CWORD`, calls `_heimdall`, and prints `COMPREPLY`. This covers:
  - a command;
  - an errand, a `/` level with `nospace`;
  - a `./` file;
  - `heimdall cd Demo r`.
- **By hand, once, in an interactive shell on the lab PC:** `heimdall run <TAB><TAB>` in a work dir. That needs the developer's own work dir: say so, and do not cd into one unasked.

## Log
