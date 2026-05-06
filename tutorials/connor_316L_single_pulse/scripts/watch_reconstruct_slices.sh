#!/usr/bin/env bash
set -u

CASE_DIR="${1:-$(pwd)}"
cd "$CASE_DIR" || exit 1

PLOTS_DIR="$CASE_DIR/slice_plots"
DONE_FILE="$PLOTS_DIR/.solverDone"
LOG_FILE="$PLOTS_DIR/slice_watcher.log"
SLICE_PYTHON="${SLICE_PYTHON:-python3}"
SLEEP_SECONDS="${SLICE_WATCH_SLEEP:-20}"

mkdir -p "$PLOTS_DIR"
: > "$LOG_FILE"

log()
{
    printf '[%s] %s\n' "$(date '+%F %T')" "$*" >> "$LOG_FILE"
}

time_sort()
{
    awk '
        function n(v) { return v + 0 }
        { print n($0), $0 }
    ' | sort -g -k1,1 | awk '{ print $2 }'
}

processor_count()
{
    find . -maxdepth 1 -type d -name 'processor*' | wc -l
}

time_ready()
{
    local t="$1"
    local n_procs="$2"
    local p

    [ "$n_procs" -gt 0 ] || return 1

    for p in $(seq 0 $((n_procs - 1))); do
        [ -d "processor${p}/${t}" ] || return 1
    done

    return 0
}

render_time()
{
    local t="$1"
    local safe_t
    safe_t="$(printf '%s' "$t" | tr './' '__')"

    if [ -f "$PLOTS_DIR/.done_${safe_t}" ]; then
        return 0
    fi

    log "Processing time $t"

    if ! reconstructPar -time "$t" >> "$LOG_FILE" 2>&1; then
        log "reconstructPar failed for $t"
        return 1
    fi

    if ! foamToVTK -time "$t" -useTimeName >> "$LOG_FILE" 2>&1; then
        log "foamToVTK failed for $t"
        return 1
    fi

    "$SLICE_PYTHON" "$CASE_DIR/scripts/write_vtk_series.py" "$CASE_DIR/VTK" >> "$LOG_FILE" 2>&1 \
        || log "write_vtk_series failed for $t (non-fatal)"

    if ! command -v "$SLICE_PYTHON" >/dev/null 2>&1; then
        log "$SLICE_PYTHON not found. Set SLICE_PYTHON=/path/to/python3"
        return 1
    fi

    vtk_file=$(find "$CASE_DIR/VTK" -maxdepth 1 -name "*_${t}.vtk" 2>/dev/null | head -1)
    if [ -z "$vtk_file" ]; then
        log "No VTK file found for time $t; skipping analyze_meltpool_vtk"
    else
        "$SLICE_PYTHON" "$CASE_DIR/scripts/analyze_meltpool_vtk.py" \
            --case "$CASE_DIR" \
            --vtk-file "$vtk_file" \
            >> "$LOG_FILE" 2>&1 \
            && log "analyze_meltpool_vtk done for $t" \
            || log "analyze_meltpool_vtk failed for $t (non-fatal)"
    fi

    touch "$PLOTS_DIR/.done_${safe_t}"
    log "Finished time $t"
}

log "Using SLICE_PYTHON=$SLICE_PYTHON"
if ! "$SLICE_PYTHON" -c "import matplotlib, numpy, pandas, pyvista, scipy" >> "$LOG_FILE" 2>&1; then
    log "$SLICE_PYTHON cannot import one or more analyze_meltpool_vtk dependencies"
fi

log "Meltpool analysis watcher started in $CASE_DIR"

while true; do
    n_procs="$(processor_count)"
    times="$(
        find processor0 -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null \
            | grep -Ev '^(constant|uniform)$' \
            | time_sort
    )"

    for t in $times; do
        time_ready "$t" "$n_procs" || continue
        sleep 2
        render_time "$t" || true
    done

    if [ -f "$DONE_FILE" ]; then
        log "Solver done marker found; final scan"
        times="$(
            find processor0 -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null \
                | grep -Ev '^(constant|uniform)$' \
                | time_sort
        )"
        for t in $times; do
            time_ready "$t" "$n_procs" || continue
            render_time "$t" || true
        done
        log "Meltpool analysis watcher exiting"
        exit 0
    fi

    sleep "$SLEEP_SECONDS"
done
