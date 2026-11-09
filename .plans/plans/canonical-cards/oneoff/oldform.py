"""P5 one-off (canonical-cards): a fixture work dir as the Heimdall before P4 leaves it, for remake.py's check. Run with the
checkout before P4, every HEIMDALL_* root in a scratch folder (none of a real work dir):

    HEIMDALL=<old checkout> HEIMDALL_WORK=… HEIMDALL_RECORDS=… HEIMDALL_RESULTS=… HEIMDALL_CACHE=… HEIMDALL_CONFIGS=<a copy
    of tests/fixtures/work/configs> HEIMDALL_RUNS=… HEIMDALL_WORKDIRS=… PYTHONPATH=<old checkout>/framework python3 oldform.py

Two Errands pool Demo/jets' pdf points in the library: lib_a, and lib_c, whose base card is lib_a's with one comment more.
Before P4 the base's bytes are in the identity, so they are two entries per point; today, one physics. Each point is complete
(a product, its identity, its provenance with a seed of its own), with a snapshot, a points.json and a plot document. One entry
of lib_a's is left with another .complete, so no Run proves it.
"""
import argparse
import json
import re
from pathlib import Path

from runner import cli, library, plotdoc, record
from runner.paths import configs_root

configs = Path(configs_root()) / "Demo"
jets = (configs / "jets.toml").read_text(encoding="utf-8")
lib_a = re.sub(r'^name\s*=\s*"jets"', 'name = "lib_a"\nlibrary = true', jets, count=1, flags=re.M)
(configs / "lib_a.toml").write_text(lib_a, encoding="utf-8")
(configs / "lib_c.toml").write_text(lib_a.replace('name = "lib_a"', 'name = "lib_c"').replace('"ep.cmnd"', '"ep_noted.cmnd"'),
                                    encoding="utf-8")
(configs / "ep_noted.cmnd").write_text("! one comment more\n" + (configs / "ep.cmnd").read_text(encoding="utf-8"),
                                       encoding="utf-8")

for number, name in enumerate(("Demo/lib_a", "Demo/lib_c")):
    p = cli.build_plans(argparse.Namespace(config=name, set=[], points=None, rerun=False, only=None), "pdf")
    record.write_snapshot(p.errand, p.configuration, p.every)
    for index, plan in enumerate(p.every):
        library.link(plan)
        plan.res.mkdir(parents=True, exist_ok=True)
        (plan.res / "jets.yoda").write_text(f"BEGIN YODA_HISTO1D_V2 /A\n# {name} {index}\nEND YODA_HISTO1D_V2\n", encoding="utf-8")
        record.provenance_file(plan).write_text(json.dumps({"format": 1, "seed": 100 * number + index + 1,
                                                            "events": plan.events, "identity": plan.identity}), encoding="utf-8")
        record.write_identity(plan)
        record.write_atomic(record.complete_marker(plan), record.marker_text(plan) + "\n")
        library.note(plan, p.errand, "created")
    record.write_atomic(p.every[0].folders.manifest, json.dumps(record.points_manifest(p.every, p.errand, p.configuration)))
    plotdoc.write(p.errand, p.configuration, p.every)
    if number == 0:
        record.write_atomic(record.complete_marker(p.every[-1]), "0" * 64 + "\n")   # an entry no Run proves
    print(name, [plan.library[:16] for plan in p.every])
