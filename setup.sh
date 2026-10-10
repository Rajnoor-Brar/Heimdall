#!/bin/bash
# setup.sh — Heimdall's environment: source it once per session (alias load_hep). Tracked; it finds
# its own folder, so a clone anywhere works (docs/framework/01_Target.md §5.8).
export HEP=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export HEP_INSTALL=$HEP/stack
[ -f "$HEP/env/machine.sh" ] && source "$HEP/env/machine.sh"     # this machine's lines (macOS: DYLD, GNU tools)
source "$HEP/env/hep_env.sh"
