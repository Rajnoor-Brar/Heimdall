# Phase 2: `record.library_key(plan)`

Status: done 2026-11-08. Blocked by: phase 1 (done).

### Step 2.1: the key (Size: S)
- Acceptance: `library_key(plan)` = sha256 of `identity_parts(plan)` with phase 1's strip list removed. It reuses `seed_basis`'s header stripping (`record.py:178`), so there is one stripping rule. The seed rule stays in the key: a manual seed is in it, identity and random are not.
- Files: `framework/runner/record.py`, `tests/runner/test_library_key.py` (new).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_library_key.py tests/runner/test_identity_golden.py`. The two probe plans give one key, a changed card line gives another, and the golden identities are unchanged.

## Log
- 2026-11-08: `record.library_parts` / `library_key`: `identity_parts` with every card line starting with the folder's `[card] comment` dropped (`seed_basis`'s rule, by the developer's word: all comments), the seed rule kept. `tests/runner/test_library_key.py` 4 pass with the golden identities (8 passed). The probe's two plans (errand and points renamed) give one key and two identities; a remark line leaves the key, a changed card line moves it. The renamed copy of the fixture config is removed after its test (the golden test plans every config in the session's scratch work).
