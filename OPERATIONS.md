# PRISM operations and recovery

## Clean setup

1. Install Python 3.12, `uv`, Node.js 24 and pnpm 10.16.1.
2. Clone the repository and copy `.env.example` to `.env`.
3. Set `PRISM_DATABASE_URL` to the SSL-required Supabase session-pooler URL.
4. Set `PRISM_SUPABASE_URL` and `PRISM_SUPABASE_PUBLISHABLE_KEY` for authenticated
   portfolio routes. Copy the same public values to `frontend/.env` using
   `frontend/.env.example`; never place a Supabase secret or service-role key in Vite variables.
5. Run `uv sync --locked --all-groups`.
6. Run `pnpm install --frozen-lockfile` in `frontend`.
7. Run `uv run alembic upgrade head`.
8. Run `uv run python -m jobs.seed_universe` and
   `uv run python -m jobs.import_nifty200`.
9. Run the first daily workflow with `uv run python -m jobs.run_daily_pipeline`.
10. Start the API and frontend using the commands in `README.md`.

## Daily workflow

Run after the market's validated daily data is available:

```powershell
uv run python -m jobs.run_daily_pipeline
```

The workflow downloads and validates prices, then calculates Layer 1 and Layer 2. New analytical
runs are committed together. A partial ingestion or calculation failure leaves the previous
successful analytical results published and records the failed stage.

For deterministic recovery using the latest already-stored snapshot:

```powershell
uv run python -m jobs.run_daily_pipeline --skip-ingestion
```

## Interrupted-run recovery

An operating-system interruption can leave a `pipeline_run` marked `running`. After confirming no
pipeline process is active, mark records older than two hours failed:

```powershell
uv run python -m jobs.recover_pipeline_runs --older-than-minutes 120
```

This changes only run status; it does not delete prices or replace published Layer 1/2 results.

## Verification

Run the read-only, real-data reproducibility and performance audit:

```powershell
uv run python -m jobs.verify_phase0
```

Run all local checks:

```powershell
uv run ruff check backend jobs tests
uv run mypy backend jobs
uv run pytest -m "not integration"
uv run alembic upgrade head --sql
uv run python -m jobs.check_repository_policy
pnpm.cmd --dir frontend lint
pnpm.cmd --dir frontend test
pnpm.cmd --dir frontend build
```

Database integration tests are deliberately opt-in because they may create a missing deterministic
run. Use only an explicitly approved PostgreSQL test database:

```powershell
$env:PRISM_RUN_DB_INTEGRATION="1"
uv run pytest -m integration
```

## Failure diagnosis

- `/api/v1/ready` checks database connectivity.
- `/api/v1/pipeline/status` reports the latest stage, last success, market/result dates and staleness.
- A `partial` market ingestion must be recovered before analytics are published.
- Never delete the last successful price or analysis revision to recover a failed run.
- Re-run migrations before diagnosing missing-table API failures.

## Database backup and restore

Always use a dedicated PostgreSQL role with the minimum required database privileges. Before an
upgrade, record the Alembic revision and create a provider snapshot or a custom-format backup:

```powershell
uv run alembic current
pg_dump --format=custom --no-owner --no-acl --file prism-before-upgrade.dump $env:PRISM_DATABASE_URL
```

Do not store dumps in the repository. Validate a backup by restoring it into an empty, isolated
database and checking both the schema and representative row counts:

```powershell
createdb prism_restore_test
pg_restore --clean --if-exists --no-owner --no-acl --dbname prism_restore_test prism-before-upgrade.dump
$env:PRISM_DATABASE_URL="postgresql+psycopg://.../prism_restore_test?sslmode=require"
uv run alembic current
uv run pytest -m integration
```

For Supabase, a platform snapshot/PITR restore is preferred when enabled. Never rehearse a restore
over the only production copy.

## Migration rehearsal and rollback

Release rehearsal has two distinct gates:

1. Clean database: create an empty PostgreSQL database and run `uv run alembic upgrade head`.
2. Existing data: restore a recent sanitized backup into an isolated database, capture critical
   row counts, run `uv run alembic upgrade head`, rerun integration tests, and compare counts.

Before deploying, render and review SQL with `uv run alembic upgrade head --sql`. To roll back one
revision, stop writes, take a backup, inspect the target with `uv run alembic history`, then run:

```powershell
uv run alembic downgrade -1
```

Some downgrades intentionally remove tables or columns. Prefer restoring the pre-upgrade backup
when a downgrade would discard data. Application rollback and schema rollback must be coordinated;
do not run older application code against an incompatible newer schema.

## Production readiness checks

- `GET /health` verifies the process is alive; `GET /api/v1/ready` verifies database access.
- Confirm `PRISM_ENVIRONMENT=production`, explicit HTTPS CORS origins, explicit trusted hosts, and
  Supabase authentication settings before startup.
- Put a shared rate limiter and TLS-terminating reverse proxy in front of multi-worker deployments.
- Logs contain request metadata and exception classes only; do not add holdings, transaction
  payloads, tokens, URLs with credentials, or raw provider responses.
- Missing providers, stale prices, and model artifacts are operational states, not reasons to
  substitute fixtures.
