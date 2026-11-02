"""framework/tools/pythia/diagnose.py — Pythia's [diagnose] (tool.toml; doc:events, V203).

App_Pythia's arguments, run after its init failed: its cards are read, in order, into one plain Pythia (App_Pythia's
PythiaParallel keeps its instances' messages to itself) and initialised, so Pythia's own reason is printed ("PYTHIA
Error in ProcessLevel::init: all processes have vanishing cross sections"). The runner's last card turns Pythia's
messages on and asks for no events. Nothing is written: the outputs are not opened.

usage: python3 diagnose.py [--threads N] [--events N] [--seeds S,…] [--sidecar FILE] OUTPUT[,OUTPUT…] CARD [CARD…]
Exit 0 when Pythia initialises, 3 when it does not (App_Pythia's Init), 2 for a card it cannot read.
"""

from __future__ import annotations

import sys

OPTIONS = {"--threads", "--events", "--seeds", "--sidecar"}       # App_Pythia's options, each with a value


def cards_of(argv: list[str]) -> list[str]:
    """The cards among App_Pythia's arguments: what follows its options and its outputs."""
    rest, value = [], False
    for arg in argv:
        if value:
            value = False
        elif arg in OPTIONS:
            value = True
        else:
            rest.append(arg)
    return rest[1:]


def main(argv: list[str]) -> int:
    cards = cards_of(argv)
    if not cards:
        print(__doc__.split("usage: ")[1].splitlines()[0], file=sys.stderr)
        return 2
    import pythia8                                                  # the stack's (PYTHONPATH: pythia8/lib)
    pythia = pythia8.Pythia("", False)                              # its banner off
    for card in cards:
        if not pythia.readFile(card):
            print(f"Error: Pythia could not read card {card}", flush=True)
            return 2
    sys.stdout.flush()
    if pythia.init():
        print("diagnose.py: one plain Pythia initialises these cards: the failure is App_Pythia's own", flush=True)
        return 0
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
