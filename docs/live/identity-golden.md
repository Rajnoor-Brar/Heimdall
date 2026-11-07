---
id: live-identity-golden
summary: every fixture point's identity parts are kept in a golden file, and a test compares them
affects: identity, testing
issue: I-11
---

**Now holds:** `tests/golden/identity_parts.json` keeps `record.identity_parts` of every point of every fixture config (193 at writing), a point a line, keyed `<Assignment>/<Errand>|<configuration>|<point>`. `tests/runner/test_identity_golden.py` plans them all and compares; a difference names the point and the first key that differs. Binaries are masked (`exe_sha256`, and the `files_sha256` entries under `/build/`, so a rebuilt app or Rivet plugin does not fail it) and the scratch folder is written `{scratch}`.

**No longer holds:** an identity change being found only by the tests of one tool. Any change to what an identity hashes now fails this test. The golden file changes only with the developer's word (an identity change reruns every point it touches), and is never regenerated to pass.

**Decisions:** I-11 was `held` in the issues and "approved" in the standing decisions (2026-10-25); the developer confirmed approval on 2026-11-07. Found while writing it: the parts of the Herwig, MadGraph and Sherpa fixture points hold an absolute path into the cache (`<scratch>/cache/…`), so those identities depend on where the cache is, unlike the `{work}`/`{apps}` paths, which are portable. The golden file masks it; it is not fixed (that would be an identity change).

**Stable pages need:** `stable/internals/identity.md` (the golden file and its rule), `stable/internals/testing.md` (the test).
