#!/bin/bash
# setup.sh — Heimdall's environment: source it once per session (alias load_hep). Tracked; it finds
# its own folder, so a clone anywhere works (docs/framework/01_Target.md §5.8).
#
#   source setup.sh                     the default stack: stack/, env/venv/, framework/Apps/
#   source stacks/<toolkit>/setup.sh    an isolated toolkit's stack (recipes/README.md §6), which asks
#                                       for it through HEP_STACK_REQUEST; `quit` the other one first
export HEP=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export HEP_STACK=${HEP_STACK_REQUEST-}
unset HEP_STACK_REQUEST
if [ -n "$HEP_STACK" ]; then
    [ -d "$HEP/stacks/$HEP_STACK/stack" ] || { echo "no stack '$HEP_STACK' in $HEP/stacks: build it (recipes/README.md §6)" >&2; return 1 2>/dev/null; }
    export HEP_INSTALL=$HEP/stacks/$HEP_STACK/stack HEP_VENV=$HEP/stacks/$HEP_STACK/venv
else
    unset HEP_STACK
    export HEP_INSTALL=$HEP/stack HEP_VENV=$HEP/env/venv
fi
source "$HEP/env/hep_env.sh"
[ -f "$HEP/env/machine.sh" ] && source "$HEP/env/machine.sh"     # this machine's lines, after hep_env.sh (macOS: DYLD, GNU tools)
return 0 2>/dev/null || true
