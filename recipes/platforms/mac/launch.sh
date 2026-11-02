#!/usr/bin/env bash
# recipes/platforms/mac/launch.sh — moved to launch.sh at Heimdall's root, which every platform uses
#. This stays for a release, for aliases made before that still point here.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/launch.sh" "$@"
