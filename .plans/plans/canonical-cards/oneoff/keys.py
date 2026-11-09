"""P5 one-off (canonical-cards): every point of every Run of a work dir, planned from the Run's own snapshot, with the
library key and identity parts that the Heimdall it is run by gives it. Read-only: it plans, and writes nothing.

    HEIMDALL=<a checkout> HEIMDALL_WORK=<work dir> PYTHONPATH=<a checkout>/framework python3 keys.py > keys.json

Run once with the checkout before P4 (the old form) and once with today's (the new form); remake.py compares them.
Each Run is planned with its own folder's number, so a configuration that numbers itself plans into that folder.
Output: one JSON line per point: {"run": "<A>/<E>/<R>", "point", "key", "parts"}; a Run that does not plan, with "error".
"""
import json
import os
from pathlib import Path

from runner import cli, paths, quantities, record, sweep
from runner.paths import records_root
from runner import config as configmod


def runs():
    for snapshot in sorted(records_root().glob(f"*/*/*/config/{record.SNAPSHOT}")):
        folder = snapshot.parent.parent
        if folder.parent.name != "library":
            yield folder


def plan_run(folder: Path):
    snap = record.read_snapshot(folder)
    os.environ[paths.CONFIGS_VAR] = str(folder / "config")
    paths.reset()
    errand, configuration = configmod.for_configuration(configmod.load(snap["config"], sets=snap.get("sets", [])),
                                                        snap["configuration"])
    head = folder.name.split("_", 1)[0]
    if head.isdigit():                                   # the Run's own folder, whatever the config would number
        configuration.serial = int(head)
        configuration.serial_auto = False
    master = quantities.load_master(errand.assignment, errand.master_toml, errand.folder)
    _, plans = cli._planned_points(errand, configuration, master, sweep.points(errand, configuration))
    return plans


def main() -> None:
    from runner import library
    for folder in runs():
        name = str(folder.relative_to(records_root()))
        try:
            plans = plan_run(folder)
        except Exception as error:                      # noqa: BLE001  (a Run that no longer plans is listed, not fatal)
            print(json.dumps({"run": name, "error": f"{type(error).__name__}: {error}"}))
            continue
        for plan in plans:
            if plan.folders.record != folder:
                print(json.dumps({"run": name, "point": plan.point.name, "error": f"planned into {plan.folders.record}"}))
                continue
            print(json.dumps({"run": name, "point": plan.point.name, "key": library.key(plan),
                              "parts": json.loads(json.dumps(record.identity_parts(plan), sort_keys=True, default=str))}))


if __name__ == "__main__":
    main()
