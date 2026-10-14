#!/usr/bin/env bash
# env/flags.sh — probe each library's *-config once and write flags.mk
# (docs/06_Internals.md §15.3).
#
#   flags.sh [OUT]     probe and write OUT: forge/make/flags.mk (Heimdall's build, framework/rules.mk),
#                      build/flags.mk (a work dir's; the default)
#   flags.sh --key     print what the cache depends on, cheaply: no probe runs
#
# framework/rules.mk compares FLAGS_KEY in the cache with `--key` on every invocation and rewrites the
# cache only when they differ; a rewrite whose flags are unchanged keeps the cache's time (no rebuild). A cache keyed on less than everything it reads is a correctness bug
# waiting for an unusual environment (ledger L22, v1's 00/B38), so the key holds the resolved path
# of every tool probed, the directories the non-config libraries come from, pkg-config's search path,
# and the stack file itself. What is probed is env/stack.toml's (V78): TOOLS, NAMES and probes() come from it.
set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
eval "$(python3 "$here/stack.py" --bash)" || { echo "flags.sh: cannot read env/stack.toml" >&2; exit 1; }

key() {
    local t
    for t in "${TOOLS[@]}"; do printf '%s=%s;' "$t" "$(command -v "$t" || echo -)"; done
    printf 'HEP_INSTALL=%s;ONNXRUNTIME_DIR=%s;DELPHES_DIR=%s;PKG_CONFIG_PATH=%s;STACK=%s' "${HEP_INSTALL-}" \
        "${ONNXRUNTIME_DIR-}" "${DELPHES_DIR-}" "${PKG_CONFIG_PATH-}" "$STACK"
}

if [ "${1-}" = "--key" ]; then key; exit 0; fi

OUT=${1:-build/flags.mk}
mkdir -p "$(dirname "$OUT")"

found=()
emit() {                                    # emit NAME FLAGS...
    local name=$1; shift
    printf 'FLAGS_%s := %s\n' "$name" "$*"
    found+=("$name")
}
probe() {                                   # probe NAME COMMAND ARGS...
    local name=$1; shift
    local out
    if command -v "$1" >/dev/null 2>&1 && out=$("$@" 2>/dev/null); then
        emit "$name" $out
    else
        printf '# %s: not found (%s)\n' "$name" "$*"
    fi
}
dir_lib() {                                 # dir_lib NAME DIR LIB — a library with no *-config
    local name=$1 dir=$2 lib=$3
    if [ -d "$dir/include" ] && [ -d "$dir/lib" ]; then
        emit "$name" "-I$dir/include" "-L$dir/lib" "-l$lib" "-Wl,-rpath,$dir/lib"
    else
        printf '# %s: not found (%s)\n' "$name" "$dir"
    fi
}

{
    echo "# flags.mk — written by env/flags.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ). Do not edit:"
    echo "# delete it, or run \`hep build --configure\`, to probe again."
    echo "FLAGS_KEY := $(key)"
    echo "KNOWN := ${NAMES[*]}"
    probes
    echo "FOUND := ${found[*]}"
} > "$OUT.tmp" || exit 1
# The same flags under a new key (env/stack.toml edited, a tool moved to an equal one): the cache keeps
# its time, so what was built with those flags is not rebuilt (every output depends on it, rules.mk).
same() { sed '1,2d;/^FLAGS_KEY := /d' "$1"; }
if [ -f "$OUT" ] && [ "$(same "$OUT")" = "$(same "$OUT.tmp")" ]; then touch -r "$OUT" "$OUT.tmp"; fi
mv "$OUT.tmp" "$OUT"

# One line per probe run, so "the second make probed nothing" is checkable (P0 S2, row 3).
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) probed: ${found[*]}" >> "$(dirname "$OUT")/flags.log"
echo "flags: probed ${#found[@]} libraries → $OUT" >&2
