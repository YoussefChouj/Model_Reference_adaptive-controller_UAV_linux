#!/usr/bin/env bash
# anti-sleep.sh — systemd-inhibit based sleep prevention for Linux
# Part of .claude/skills/anti-sleep/

set -euo pipefail

CACHE_DIR="${HOME}/.cache/anti-sleep"
PID_FILE="${CACHE_DIR}/pid"
EXPIRY_FILE="${CACHE_DIR}/expiry"
LABEL="anti-sleep-agent"

mkdir -p "$CACHE_DIR"

get_status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        local pid expiry
        pid=$(cat "$CACHE_DIR/pid")
        expiry=$(cat "$CACHE_DIR/expiry" 2>/dev/null || echo "unknown")
        local remaining
        remaining=$(( $(date -d "$expiry" +%s 2>/dev/null || echo 0) - $(date +%s) ))
        echo "STATUS=running"
        echo "PID=$pid"
        echo "EXPIRY=$expiry"
        echo "REMAINING=$remaining seconds"
    else
        echo "STATUS=stopped"
    fi
}

do_start() {
    local duration="${1:-10800}"  # default 3 hours
    local expiry
    expiry=$(date -d "+${duration} seconds" -Iseconds)

    # Stop any existing session
    if [ -f "$PID_FILE" ]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null || true
    fi

    # Launch inhibit loop in background
    (
        while true; do
            systemd-inhibit --who="$LABEL" --why="Agent session active" --mode=block sleep 3600 2>/dev/null || exit 0
        done
    ) &
    local pid=$!

    echo "$pid" > "$CACHE_DIR/pid"
    echo "$expiry" > "$CACHE_DIR/expiry"

    echo "Started anti-sleep: PID=$pid, expires=$expiry"
}

do_stop() {
    if [ -f "$PID_FILE" ]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null && echo "Stopped." || echo "Already stopped."
    else
        echo "Already stopped."
    fi
    rm -f "$CACHE_DIR/pid" "$CACHE_DIR/expiry"
}

do_verify() {
    get_status
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$CACHE_DIR/pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "ASSERTIONS=active"
            return 0
        fi
    fi
    echo "ASSERTIONS=none"
    return 1
}

case "${1:-status}" in
    start)    do_start "${2:-10800}" ;;
    stop)     do_stop ;;
    status)   get_status ;;
    verify)   do_verify ;;
    *)        echo "Usage: $0 {start <secs>|stop|status|verify}" >&2; exit 1 ;;
esac
