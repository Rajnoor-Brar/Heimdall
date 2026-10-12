# 07 — P4: Verified, and handed over

**Goal.**
- **S1:** the physics on the new install matches the lab PC's:
  - the slow suite's gates (P2 S2) are settled;
  - one real point, the reference, is re-run on its seed and compared against the products kept
    before the wipe.
- **S2:** the handover:
  - the plans' state, the agents' rules and memory;
  - the report;
  - Heimdall published, which is a gate;
  - the stack's build trees cleaned.

**Reads:** 01 §8 (what was kept), P2 S2's rows.

**Writes:**
- a scratch work dir for the reference point, `$HEP/.setup/verify/P4/ref`;
- Heimdall's `bots/current_plan.md`;
- `$HEP/.setup/report.md`.

**Gates:**
- a reference setup that differs from the kept one (S1);
- publishing, the agents' memory, the shell's `load_hep` alias (S2).

---

## S1: the physics

**Preconditions:**
- P3 is verified.
- P2 S2 is `done`, with its R2 decided if it failed.
- The machine is otherwise idle: the reference uses 12 threads plus 10 Rivets.

**The reference point** (kept as `$HEP/.setup/kept/reference/`, 01 §8) is the point that the
fixture's `Demo/inproc_validation`, configuration `default`, calls `NNPDF23lo`. Its provenance on the
lab PC says:

| | |
|---|---|
| ran | 2026-10-06, 06:47–06:49 UTC, 90.7 s (InprocJets) |
| events | 1,000,000 asked; 999,892 written (`sum_w` 999,892) |
| threads, seed | 12, 246223968 |
| values | `pdf` NNPDF23lo (Pythia's set 13), `energies` 27x920, `lepton` ep, `pt0ref` 3.2 |
| σ | 72,987.1229835 ± 30.3402721 pb (from the generator) |
| `/RAW/…/d01-x01-y01`, `d02-x01-y01` | 22,423 entries each |
| its YODA, `cards/pythia.point.cmnd` | sha256 `0db5cc2e327680ee…`, `51d0db61bc8ec901…` |

**Tasks:**

1. **A scratch work dir with the reference's project,** filled from Heimdall's own fixture work dir
   (frozen copies of the study's configs and modules, and `jets_data.yoda`, V112),
   so no High-Energy clone is needed:
   ```bash
   R=$HEP/.setup/verify/P4/ref && hep setup $R
   cp -r $HEP/tests/fixtures/work/{configs,modules,datasets} $R/
   cd $R && hep build && touch $R/stamp
   ```
2. **Plan it** with its seed pinned (the fixture's `inproc_validation.toml` already asks for 12 threads):
   ```bash
   SETS=(--set 'run.cfgs.default.threads=12' --set 'run.cfgs.default.seed_type="manual"' --set 'run.cfgs.default.manual_seed=246223968')
   hep run Demo/inproc_validation default --points NNPDF23lo "${SETS[@]}" --plan
   ```
   **The setup is the same:** diff the point card and the program's config against the kept ones.
   Comment lines are skipped, and the config's paths differ by place:
   ```bash
   K=$HEP/.setup/kept/reference/output
   N=$(ls -d $R/output/Demo/inproc_validation/*default/NNPDF23lo)
   diff <(grep -v '^ *!' $K/cards/pythia.point.cmnd) <(grep -v '^ *!' $N/cards/pythia.point.cmnd)
   diff <(grep -v '/' $K/config/inproc.toml) <(grep -v '/' $N/config/inproc.toml)
   ```
   (The plan writes the cards. If `--plan` does not, run task 3 first and diff after.)
   - **A difference is a gate.** The fixture's configs were frozen on 2026-10-03, and the reference
     ran on 10-06 with the user's configs of that day, so the comparison below could be of two
     setups. Show the diff, and the user decides: compare anyway (the rows become informative
     only), or pin the changed keys too.
3. **Run it:** the same command without `--plan`, with `--plain`. It took about 90 s on the lab PC.
4. **Compare.** Write `$HEP/.setup/compare_ref.py`, tested on the lab PC (the kept files against
   themselves: all `same`, exit 0):
   ```python
   #!/usr/bin/env python3
   """compare_ref.py KEPT NEW: the reference point (07 S1), kept from the lab PC, against its rerun.

   KEPT and NEW are the point's results folders: each holds one YODA and its .json. Prints one line per
   quantity: kept, new, difference, the allowed difference, and "same", "ok" or "FAIL". Exit 1 on a FAIL.
   Allowed: 3 standard deviations of a difference of two independent estimates (sqrt 2), or exact equality."""
   import json, math, re, sys
   from pathlib import Path


   def raw_entries(yoda: Path, name: str) -> float:
       text = yoda.read_text(encoding="utf-8")
       m = re.search(rf"BEGIN YODA_HISTO1D_V3 /RAW/ZEUS_2012_I1116258/{name}\n(.*?)END", text, re.S)
       rows = [line.split() for line in m.group(1).splitlines() if line[:1] in "0123456789-." and len(line.split()) >= 5]
       return sum(float(r[-1]) for r in rows)


   def main(kept: Path, new: Path) -> int:
       [ky], [ny] = sorted(kept.glob("*.yoda")), sorted(new.glob("*.yoda"))
       a = json.loads(Path(f"{ky}.json").read_text(encoding="utf-8"))
       b = json.loads(Path(f"{ny}.json").read_text(encoding="utf-8"))
       rows = [("sigma_pb", a["sigma_pb"], b["sigma_pb"], 3 * math.sqrt(a["sigma_err_pb"] ** 2 + b["sigma_err_pb"] ** 2)),
               ("events", a["events"], b["events"], 3 * math.sqrt(2 * (1e6 - a["events"]) + 1))]
       for name in ("d01-x01-y01", "d02-x01-y01"):
           x, y = raw_entries(ky, name), raw_entries(ny, name)
           rows.append((f"{name} entries", x, y, 3 * math.sqrt(x + y)))
       bad = 0
       for name, x, y, allowed in rows:
           verdict = "same" if x == y else "ok" if abs(x - y) <= allowed else "FAIL"
           bad += verdict == "FAIL"
           print(f"{name:20s} kept {x:.10g}  new {y:.10g}  diff {y - x:+.4g}  allowed ±{allowed:.4g}  {verdict}")
       return 1 if bad else 0


   sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
   ```
   Then run:
   ```bash
   python3 $HEP/.setup/compare_ref.py \
       $HEP/.setup/kept/reference/results \
       $(ls -d $R/results/Demo/inproc_validation/*default/NNPDF23lo)
   ```
   - **`same` everywhere:** the new build generates the same events on the same seed, which is
     the strongest result.
   - **`ok`:** different events (a new compiler or libm), the same physics within 3σ.
   - **`FAIL`:** a gate.
5. Record the verdict per quantity in `state.toml`, and P2 S2's outcome next to it.

**Verification:**

| # | Command | Expected |
|---|---|---|
| R1 | task 2's two `diff`s, `\| wc -l` | `0` and `0` (or the user's decision at the gate) |
| R2 | task 4's `compare_ref.py …; echo "exit $?"` | four lines, each `same` or `ok`; `exit 0` |
| R3 | `python3 -c "import json; d=json.load(open('$(ls -d $R/results/Demo/inproc_validation/*default/NNPDF23lo)/validation.yoda.json')); print(d['sigma_from'], d['stopped'])"` | `generator False` |
| R4 | `git -C $HEP status --porcelain \| wc -l; find $HEP -newer $R/stamp -not -path "$HEP/.setup/*" -not -path '*/__pycache__*' \| wc -l` | `0` and `0` (the run wrote nothing in Heimdall) |
| R5 | P2 S2 R1–R10 in `state.toml` | all `done`, with R2 either byte-identical or decided by the user (a V-row) |

**On failure:** R2's `FAIL` on σ but not on the entries, or the other way round, is the more
informative case. Keep both outputs, and report `sigma_from` and the threads that actually ran.

---

## S2: the handover

**Preconditions:** S1 `done`, and every earlier phase `verified`.

**Tasks:**

1. **Heimdall's `bots/current_plan.md`:**
   - the machine is set up, with the date, Heimdall's revision, and the numbers of S1 and P2;
   - **what is still open**, carried in it from before (`docs/audit_2/01_Health.md`, the items
     "Later", `bots/intent.md`), and High-Energy's parked conversion (06's appendix).

   Commit.
2. **The report**, `$HEP/.setup/report.md`, one page:
   - the phases with their times;
   - every gate and its answer;
   - every deviation and where it was folded in;
   - the disk used (`du -sh $HEP_MACHINE/{stack,venv,forge,apps}/`);
   - P2's test counts;
   - S1's table;
   - **"how to work now"** in five lines:
     ```bash
     source ~/Github/Heimdall/setup.sh     # load_hep
     cd ~/Github/Top-Quark && hep run Starter/starter --plan
     hep setup ~/Github/<new> --project <P> --git     # another work dir
     hep build --framework                 # after changing Heimdall's apps (identities change, 06 §27)
     hep where                             # which Heimdall and work dir this shell sees
     ```
3. **Clean the stack's build trees.** The stack's trees in `$HEP_MACHINE/forge/build/` (6.8 GB on the
   lab PC) and the unpacked sources in `forge/src/` go. The archives in `forge/downloads/`, and
   `forge/logs/`, `forge/make/`, `forge/tests/`, `forge/scratch/` stay. This is inside
   `$HEP_MACHINE/forge`, so 02 §6 needs no gate; report the space freed. Never `git clean -x`.
4. **Gates, asked together, each answered on its own:**
   - **publish Heimdall:** if it was cloned from a bundle, a new private GitHub repository
     `Rajnoor-Brar/Heimdall` (the user creates it, or approves `gh repo create --private`), then
     `git push -u origin main`; otherwise push the commits these phases made;
   - **Top-Quark:** keep it local, or give it a remote (the user's choice; it is a test);
   - **`load_hep`:** add `alias load_hep='source ~/Github/Heimdall/setup.sh'` to `~/.bashrc`;
   - **the agents' memory:** copy `$HEP/.setup/kept/memory/` (if it was kept, 01 §8) back to
     the agents' memory folder for `~/Github/Heimdall`, and update its lab-PC entries to the new
     install (Heimdall at `~/Github/Heimdall`, Top-Quark, High-Energy left alone);
   - **the user's kept folders** (`datasets/ literature/ cross_machine/ reports/` in
     `$HEP/.setup/kept/`): where they go is the user's.

**Verification:**

| # | Command | Expected |
|---|---|---|
| R1 | `python3 -c "import tomllib; s=tomllib.load(open('$HEP/.setup/state.toml','rb'))['step']; print(sum(v['status']!='done' for v in s.values()))"` | `0` |
| R2 | `python3 -c "import tomllib; d=tomllib.load(open('$HEP/.setup/state.toml','rb')).get('deviation',[]); print(sum(not x['folded'] for x in d))"` | `0` (every deviation folded into the plans) |
| R3 | `git -C $HEP status --porcelain \| wc -l` | `0` |
| R4 | `test -s $HEP/.setup/report.md && grep -c '^## ' $HEP/.setup/report.md` | ≥ `5` |
| R5 | `ls -d $HEP_MACHINE/forge/build/root $HEP_MACHINE/forge/build/geant4 2>/dev/null \| wc -l` | `0` (the stack's trees are gone) |
| R6 | `bash -lc 'source ~/Github/Heimdall/setup.sh >/dev/null; cd ~/Github/Top-Quark && hep where'` | two lines: `hep=…/Github/Heimdall <revision>`, `work=…/Github/Top-Quark` |
| R7 | `ls $HEP_MACHINE/stack/.stamps \| wc -l` | `20` (the cleaning left the installs) |
