#!/usr/bin/env bash
#
# Start SIMBA. One command, cleaned up on Ctrl+C.
#
# The argument is the page the window opens on, not the task. What you type
# into SIMBA chooses the task, and every real start page brings up both
# replicas, so any flow can be asked for from any of them.
#
#   ./run.sh                 opens on the registration replica
#   ./run.sh billing         opens on the billing replica
#   ./run.sh railways        opens on the live public site (read-only)
#   ./run.sh mock            overlay + scripted backend, nothing real
#
# SIMBA_RUN_SECONDS=20 ./run.sh mock starts everything, waits, and shuts down
# again. A smoke test: it proves the pieces come up and that cleanup works,
# without a person having to press anything.
#
# The hardcoded plan is the default everywhere on purpose: it spends no API
# quota and it is deterministic, so a run that misbehaves is the system's
# fault rather than the model's. For the LLM, add SIMBA_USE_HARDCODED_PLAN=0.
#
# See RUNNING.md for what each start page shows and what to do when one fails.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

START_PAGE="${1:-registration}"
BACKEND_PORT="${SIMBA_BACKEND_PORT:-8000}"
CDP_PORT="${SIMBA_CDP_PORT:-9222}"

# Electron reads this and runs as plain Node when it is set: no window, no
# CDP, and an error naming our entry point rather than the real cause. Some
# editors set it in their integrated terminal, which is exactly where someone
# is most likely to run this.
unset ELECTRON_RUN_AS_NODE

PIDS=()
PORTS=()
STOPPED=0

case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*) WINDOWS=1 ;;
  *) WINDOWS=0 ;;
esac

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31m!!\033[0m %s\n' "$*" >&2; exit 1; }

port_busy() { # port
  if [ "$WINDOWS" = 1 ]; then
    netstat -ano 2>/dev/null | grep -qE "LISTENING" \
      && netstat -ano 2>/dev/null | grep -E "LISTENING" | grep -qE ":$1[[:space:]]"
  else
    lsof -ti "tcp:$1" >/dev/null 2>&1
  fi
}

kill_port() { # port
  # Killing by listening port rather than by recorded pid, because the thing
  # to stop is rarely the thing that was started: `npm start` becomes node
  # becomes electron.exe plus five helpers, and none of those die when their
  # launcher does. The port is the one handle that reaches the process
  # actually holding the resource — and the pre-flight check below means
  # anything on these ports is ours.
  if [ "$WINDOWS" = 1 ]; then
    netstat -ano 2>/dev/null | grep -E "LISTENING" | grep -E ":$1[[:space:]]" \
      | awk '{print $NF}' | sort -u | while read -r wpid; do
        # //T takes the process tree with it; MSYS rewrites // to /.
        [ -n "$wpid" ] && taskkill //F //T //PID "$wpid" >/dev/null 2>&1
      done
  else
    lsof -ti "tcp:$1" 2>/dev/null | xargs -r kill -9 2>/dev/null
  fi
}

cleanup() {
  local status=$?
  # INT or TERM runs this, and then so does EXIT. Once is enough.
  [ "$STOPPED" = 1 ] && exit $status
  STOPPED=1

  printf '\n'
  say "stopping"
  for pid in "${PIDS[@]:-}"; do
    [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null
  done
  for port in "${PORTS[@]:-}"; do
    [ -n "${port:-}" ] && kill_port "$port"
  done
  say "stopped"
  exit $status
}
trap cleanup INT TERM EXIT

# The backend's venv if it exists, so nobody has to remember to activate it.
if [ -x backend/venv/Scripts/python.exe ]; then
  PY=backend/venv/Scripts/python.exe
elif [ -x backend/venv/bin/python ]; then
  PY=backend/venv/bin/python
else
  PY="${PYTHON:-python}"
  warn "no backend/venv found, using '$PY' from PATH"
fi

wait_for() { # url, what, seconds
  local url="$1" what="$2" limit="${3:-60}" waited=0
  while [ "$waited" -lt "$limit" ]; do
    if curl -s -o /dev/null --max-time 2 "$url"; then
      say "$what is up"
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  die "$what did not come up at $url after ${limit}s — see the log above"
}

start_replica() { # name, port
  local name="$1" port="$2"
  say "starting the $name replica on :$port"
  PORTS+=("$port")
  PORT="$port" "$PY" "replicas/$name/app.py" &
  PIDS+=($!)
  wait_for "http://127.0.0.1:$port/" "the $name replica" 30
}

start_host() { # start url
  if [ ! -d frontend/node_modules ]; then
    say "installing frontend dependencies (first run only)"
    (cd frontend && npm install) || die "npm install failed"
  fi
  say "starting the Electron host (builds first, ~10s)"
  PORTS+=("$CDP_PORT")
  (cd frontend && SIMBA_START_URL="$1" SIMBA_CDP_PORT="$CDP_PORT" npm start) &
  PIDS+=($!)
  wait_for "http://127.0.0.1:$CDP_PORT/json/version" "the host (CDP $CDP_PORT)" 120
}

start_backend() {
  # No SIMBA_FLOW: the typed goal chooses the task (2026-09-21), and setting
  # it here only made the backend's health check name the start page as if it
  # were the task. One set in the calling shell — `stubborn` — passes through.
  say "starting the backend on :$BACKEND_PORT — the typed goal picks the task, planner=${PLANNER_NAME}"
  PORTS+=("$BACKEND_PORT")
  SIMBA_BROWSER=electron \
  SIMBA_CDP_URL="http://127.0.0.1:$CDP_PORT" \
  SIMBA_USE_HARDCODED_PLAN="${SIMBA_USE_HARDCODED_PLAN:-1}" \
    "$PY" -m uvicorn backend.orchestrator.app:app --port "$BACKEND_PORT" &
  PIDS+=($!)
  wait_for "http://127.0.0.1:$BACKEND_PORT/" "the backend" 45
}

# Refuse to start on top of another run. Without this the second launcher
# attaches to the first one's host and backend without saying so, and its
# cleanup then kills processes it did not start.
for port in "$BACKEND_PORT" "$CDP_PORT" 5000 5100; do
  if port_busy "$port"; then
    die "port $port is already in use — another SIMBA run is probably up. Stop that one first."
  fi
done

if [ "${SIMBA_USE_HARDCODED_PLAN:-1}" = "1" ]; then
  PLANNER_NAME="hardcoded (no API quota spent)"
else
  PLANNER_NAME="LLM (spends API quota)"
fi

case "$START_PAGE" in
  # Since 2026-09-21 the typed goal chooses the flow, not this argument, so
  # every real flow's site has to be up whichever page is named. The name
  # only chooses the page the host opens on.
  registration)
    start_replica registration 5000
    start_replica billing 5100
    start_host "http://127.0.0.1:5000"
    start_backend
    ;;
  billing)
    start_replica registration 5000
    start_replica billing 5100
    start_host "http://127.0.0.1:5100"
    start_backend
    ;;
  railways)
    warn "railways is a live public website. Read-only, and please do not"
    warn "hammer it — a handful of runs, not a benchmark."
    start_replica registration 5000
    start_replica billing 5100
    start_host "https://www.pakrailways.gov.pk/train"
    start_backend
    ;;
  mock)
    # No replica and no real backend: the scripted one plays the backend's
    # whole side of the conversation, including a mid-task level change, so
    # the fold between detail levels can be watched without a site at all.
    say "starting the mock backend on :$BACKEND_PORT (scripted, no browser driving)"
    PORTS+=("$BACKEND_PORT")
    "$PY" -m uvicorn tools.mock_backend:app --port "$BACKEND_PORT" &
    PIDS+=($!)
    wait_for "http://127.0.0.1:$BACKEND_PORT/" "the mock backend" 30
    start_host "about:blank"
    ;;
  *)
    die "unknown start page '$START_PAGE' — expected registration, billing, railways or mock"
    ;;
esac

printf '\n'
say "ready — type a goal in the SIMBA window and press Start"
if [ "$START_PAGE" = "mock" ]; then
  say "the level changes itself before step 3 and back before step 4: watch the fold"
fi
say "Ctrl+Shift+D in the window shows the message log"
say "Ctrl+C here stops everything"
printf '\n'

if [ -n "${SIMBA_RUN_SECONDS:-}" ]; then
  say "SIMBA_RUN_SECONDS=$SIMBA_RUN_SECONDS, shutting down after that"
  sleep "$SIMBA_RUN_SECONDS"
else
  wait
fi
