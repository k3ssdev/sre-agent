#!/bin/sh
set -eu

run_agent() {
    while :; do
        sre-agent || true
        sleep "${AGENT_INTERVAL_SECONDS:-600}"
    done
}

run_daily_report() {
    while :; do
        now=$(date +%s)
        target=$(date -d 'today 09:00' +%s)
        if [ "$target" -le "$now" ]; then
            target=$(date -d 'tomorrow 09:00' +%s)
        fi
        sleep "$((target - now))"
        sre-agent --daily-report || true
    done
}

case "${1:-all}" in
    all)
        run_agent & agent_pid=$!
        run_daily_report & daily_report_pid=$!
        sre-agent --telegram-bot & bot_pid=$!
        trap 'kill "$agent_pid" "$daily_report_pid" "$bot_pid" 2>/dev/null || true' INT TERM EXIT
        wait "$bot_pid"
        ;;
    agent)
        run_agent
        ;;
    daily-report)
        run_daily_report
        ;;
    bot)
        exec sre-agent --telegram-bot
        ;;
    *)
        exec "$@"
        ;;
esac