#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

command -v pnpm >/dev/null 2>&1 || { echo 'Install pnpm before starting PRISM.' >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo 'Install curl before starting PRISM.' >&2; exit 1; }

backend_pid=''
frontend_pid=''
cleanup() {
    trap - EXIT INT TERM
    [[ -z "$frontend_pid" ]] || kill "$frontend_pid" 2>/dev/null || true
    [[ -z "$backend_pid" ]] || kill "$backend_pid" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

api_ready() {
    local health
    health="$(curl --noproxy '*' --silent --fail --max-time 2 http://127.0.0.1:8000/health)" || return 1
    [[ "$health" =~ \"service\"[[:space:]]*:[[:space:]]*\"prism-api\" ]]
}

if api_ready; then
    echo 'Using the PRISM API already running at http://127.0.0.1:8000.'
else
    echo 'Starting the PRISM API at http://127.0.0.1:8000...'
    ./backend/run.sh --host 127.0.0.1 --port 8000 &
    backend_pid=$!
    ready=false
    for ((attempt=0; attempt<60; attempt++)); do
        if ! kill -0 "$backend_pid" 2>/dev/null; then
            echo 'The API failed to start. Check the backend error above; the frontend has not been started.' >&2
            exit 1
        fi
        if api_ready; then
            ready=true
            break
        fi
        sleep 1
    done
    if [[ "$ready" != true ]]; then
        echo 'The API did not become ready. Check the backend output and whether port 8000 is in use.' >&2
        exit 1
    fi
fi

echo 'Starting the frontend at http://localhost:5173. Press Ctrl+C to stop services started here.'
pnpm --dir frontend dev --strictPort &
frontend_pid=$!

# Stop the other service as well if either service exits or fails to start.
while kill -0 "$frontend_pid" 2>/dev/null; do
    if [[ -n "$backend_pid" ]] && ! kill -0 "$backend_pid" 2>/dev/null; then
        echo 'The API stopped. Check the backend error above.' >&2
        wait "$backend_pid"
        exit 1
    fi
    sleep 1
done
wait "$frontend_pid"
