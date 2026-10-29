#!/bin/sh
set -eu
# One process: schedulers and rate limiting are process-local.
exec uvicorn deploy.app:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers
