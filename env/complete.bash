#!/bin/bash
# env/complete.bash — TAB completion for `heimdall` (tab-complete). Sourced by heimdall_env.sh beside the shell functions, so
# every shell that loads Heimdall has it and nothing is installed; `quit` takes it out again.
#
# `heimdall cd`, `refresh` and `quit` are the shell function's own and are answered here. Everything else is the program's:
# `heimdall __complete CWORD WORD…` (framework/runner/complete.py) answers with the candidates one a line and a last line
# that starts with a colon, the directive: ":plain", ":nospace" (the candidates end in "/" and the word goes on),
# ":files:PATTERN" (this shell completes files and folders, the files by PATTERN; empty: all) or ":dirs".

_heimdall_fill() {                              # COMPREPLY gets what the command it is given prints, a line each
    local line
    while IFS= read -r line; do COMPREPLY+=("$line"); done < <("$@" 2>/dev/null)
}

_heimdall() {
    local cur=${COMP_WORDS[COMP_CWORD]-} out directive line n
    local -a lines=()
    COMPREPLY=()
    case "${COMP_WORDS[1]-}" in
        refresh|quit) return 0 ;;
        cd)
            if [ "$COMP_CWORD" -eq 2 ]; then
                local work
                work=$(command heimdall where --work 2>/dev/null) || return 0
                [ -d "$work/configs" ] && _heimdall_fill bash -c 'cd "$1" && compgen -d -- "$2"' _ "$work/configs" "$cur"
            elif [ "$COMP_CWORD" -eq 3 ]; then
                _heimdall_fill compgen -W "configs modules results records logs" -- "$cur"
            fi
            return 0 ;;
    esac
    out=$(command heimdall __complete "$COMP_CWORD" "${COMP_WORDS[@]:1}" 2>/dev/null) || return 0
    while IFS= read -r line; do lines+=("$line"); done <<< "$out"
    n=${#lines[@]}
    [ "$n" -gt 0 ] || return 0
    directive=${lines[$((n - 1))]#:}
    unset "lines[$((n - 1))]"
    case "$directive" in
        nospace)
            type compopt >/dev/null 2>&1 && compopt -o nospace          # bash before 4 has no compopt: the space stays
            COMPREPLY=("${lines[@]}") ;;
        dirs)
            type compopt >/dev/null 2>&1 && compopt -o filenames
            _heimdall_fill compgen -d -- "$cur" ;;
        files:*)
            local pattern=${directive#files:} extglob=0
            type compopt >/dev/null 2>&1 && compopt -o filenames
            shopt -q extglob && extglob=1 || shopt -s extglob
            _heimdall_fill compgen -d -- "$cur"
            if [ -n "$pattern" ]; then _heimdall_fill compgen -f -X "!$pattern" -- "$cur"; else _heimdall_fill compgen -f -- "$cur"; fi
            [ "$extglob" -eq 1 ] || shopt -u extglob ;;
        *)
            COMPREPLY=("${lines[@]}") ;;
    esac
    return 0
}

complete -F _heimdall heimdall
