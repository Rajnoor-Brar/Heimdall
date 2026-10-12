#!/usr/bin/env bash
# recipes/platforms/mac/launch.sh — moved to launch.sh at Heimdall's root, which every platform uses
# (docs/audit_3/06_Plan.md, phase 3.3). This stays for a release, for `load_hep` aliases made before.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/launch.sh" "$@"
