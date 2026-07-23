#!/usr/bin/env bash
#
# bot.sh -- start/stop the checkout bot DETACHED from your terminal.
#
# "Detached" means the bot keeps running after you close the terminal window.
# It uses `nohup` (ignore the hang-up signal a closing terminal sends) plus `&`
# (run in the background), and records the process ID in a .bot.pid file so we
# can stop it later.
#
# IMPORTANT: this keeps running only while your Mac is ON and AWAKE. If the Mac
# sleeps (e.g. you close the lid), the bot is suspended and disconnects. For
# always-on-even-when-your-Mac-is-off, see docs/HOSTING.md.
#
# Usage:
#   ./bot.sh start     # launch in the background
#   ./bot.sh stop      # stop it
#   ./bot.sh status    # is it running?
#   ./bot.sh logs      # follow the live log (Ctrl+C to stop watching)

set -euo pipefail
cd "$(dirname "$0")"           # always operate from the project folder

PIDFILE=".bot.pid"
LOGFILE="bot.log"
PY=".venv/bin/python"

is_running() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

start() {
  if is_running; then
    echo "Bot is already running (PID $(cat "$PIDFILE"))."
    return 0
  fi
  # -u = unbuffered output, so the log updates live instead of in chunks.
  nohup "$PY" -u src/bot.py > "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  echo "Bot started (PID $(cat "$PIDFILE"))."
  echo "Logs -> $LOGFILE   (watch with: ./bot.sh logs)"
}

stop() {
  if is_running; then
    kill "$(cat "$PIDFILE")"
    rm -f "$PIDFILE"
    echo "Bot stopped."
  else
    echo "Bot is not running."
    rm -f "$PIDFILE"
  fi
}

status() {
  if is_running; then
    echo "Bot is running (PID $(cat "$PIDFILE"))."
  else
    echo "Bot is not running."
  fi
}

case "${1:-}" in
  start)  start ;;
  stop)   stop ;;
  status) status ;;
  logs)   tail -n 40 -f "$LOGFILE" ;;
  *)      echo "Usage: ./bot.sh {start|stop|status|logs}"; exit 1 ;;
esac
