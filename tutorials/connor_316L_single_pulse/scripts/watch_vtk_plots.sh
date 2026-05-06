#!/usr/bin/env bash
# watch_vtk_plots.sh  –  Run analyze_meltpool_vtk.py for every new VTK file.
# Usage:  ./scripts/watch_vtk_plots.sh [CASE_DIR]
# Launched automatically by Allrun; can also be run standalone.

set -u

CASE_DIR="${1:-$(pwd)}"
VTK_DIR="$CASE_DIR/VTK"
DONE_MARKER="$CASE_DIR/post-processing-data/.vtk_watcher_done"
LOG="$CASE_DIR/post-processing-data/vtk_plot_watcher.log"
PYTHON="${PLOT_PYTHON:-python3}"
SLEEP="${VTK_WATCH_SLEEP:-15}"

mkdir -p "$CASE_DIR/post-processing-data"
: > "$LOG"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }

processed_key() {
    # Use a hidden stamp file per VTK so we never re-process
    local vtk="$1"
    local base
    base=$(basename "$vtk" .vtk)
    echo "$CASE_DIR/post-processing-data/.plotdone_${base}"
}

process_vtk() {
    local vtk="$1"
    local stamp
    stamp=$(processed_key "$vtk")
    [ -f "$stamp" ] && return 0          # already done

    log "Plotting $vtk"
    if "$PYTHON" "$CASE_DIR/scripts/analyze_meltpool_vtk.py" \
            --case "$CASE_DIR" \
            --vtk-file "$vtk" >> "$LOG" 2>&1; then
        touch "$stamp"
        log "Done: $(basename "$vtk")"
    else
        log "FAILED: $(basename "$vtk") (will retry)"
    fi
}

log "VTK plot watcher started. Watching $VTK_DIR"

while true; do
    if [ -d "$VTK_DIR" ]; then
        for vtk in "$VTK_DIR"/*.vtk; do
            [ -f "$vtk" ] || continue
            process_vtk "$vtk"
        done
    fi

    if [ -f "$DONE_MARKER" ]; then
        log "Done marker found; final sweep"
        if [ -d "$VTK_DIR" ]; then
            for vtk in "$VTK_DIR"/*.vtk; do
                [ -f "$vtk" ] || continue
                process_vtk "$vtk"
            done
        fi
        log "VTK plot watcher exiting"
        exit 0
    fi

    sleep "$SLEEP"
done
