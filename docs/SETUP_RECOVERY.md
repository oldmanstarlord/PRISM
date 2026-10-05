# PRISM Setup and Recovery Guide

This document describes how to bring PRISM up from scratch on a fresh machine,
restore it from a Supabase backup, and run each major job.  It closes SRS
Section 16 item: *"Setup and recovery instructions have been tested by another
team member."*

> [!IMPORTANT]
> **All secret values (passwords, keys, connection strings) are provided by
> name only in this document.  Never commit actual values to the repository.**

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Clone and environment](#2-clone-and-environment)
3. [Environment variables (names only)](#3-environment-variables-names-only)
4. [Python environment](#4-python-environment)
5. [Database: run migrations](#5-database-run-migrations)
6. [Database: seed initial data](#6-database-seed-initial-data)
7. [Ingest market data](#7-ingest-market-data)
8. [Run scheduled jobs](#8-run-scheduled-jobs)
9. [Start the API server](#9-start-the-api-server)
10. [Start the frontend dev server](#10-start-the-frontend-dev-server)
11. [Run tests and linters](#11-run-tests-and-linters)
12. [Restore from a Supabase backup](#12-restore-from-a-supabase-backup)
13. [Teammate sign-off checklist](#13-teammate-sign-off-checklist)

---

## 1. Prerequisites

| Tool | Version | How to get it |
|---|---|---|
| Python | 3.12.x | <https://www.python.org/downloads/> or `pyenv install 3.12` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (Unix) or see <https://github.com/astral-sh/uv> |
| Node.js | 20.x LTS | <https://nodejs.org/> or `nvm install 20` |
| pnpm | 10.x | `npm install -g pnpm@10` |
| Git | any recent | <https://git-scm.com/> |
| Supabase project | existing | Supabase dashboard — see Section 12 for restore |

Verify versions:

```bash
python --version    # 3.12.x
uv --version        # 0.x.y
node --version      # v20.x.y
pnpm --version      # 10.x.y
```

---

## 2. Clone and environment

```bash
git clone <REPOSITORY_URL> PRISM
cd PRISM
```

Copy the environment template and fill in the values listed in Section 3:

```bash
cp .env.example .env
# Open .env and fill in every variable
```

---

## 3. Environment variables (names only)

The `.env` file must define the following variables.  **Values are not listed
here.  Obtain them from the project secret store or a trusted team member.**

| Variable | Purpose |
|---|---|
| `PRISM_ENVIRONMENT` | Runtime mode (`development` / `production`) |
| `PRISM_API_HOST` | Host the FastAPI server binds to |
| `PRISM_API_PORT` | Port the FastAPI server listens on |
| `PRISM_DATABASE_URL` | Full PostgreSQL connection URL (Supabase session-pooler, SSL required) |
| `PRISM_MIGRATION_DATABASE_URL` | Connection URL for Alembic migrations (optional; falls back to `PRISM_DATABASE_URL`) |
| `PRISM_CORS_ORIGINS` | JSON array of allowed origins (e.g. `["http://localhost:5173"]`) |

> [!CAUTION]
> Never commit `.env` to Git.  It is listed in `.gitignore`.  Never print
> `PRISM_DATABASE_URL` in logs or shell history.

---

## 4. Python environment

```bash
# Create the venv and install all dependencies (including dev extras).
uv sync --dev

# Verify the environment is usable.
uv run python -c "import backend; print('backend OK')"
```

ASSUMPTION: `uv` is on `PATH`.  On Windows, the installer adds it to
`%USERPROFILE%\.cargo\bin` or `%USERPROFILE%\.local\bin`; restart your shell if
not found.

---

## 5. Database: run migrations

> [!IMPORTANT]
> Migrations are **additive only** and are reviewed before merging.  Never
> apply migrations in production without reading the rendered SQL first.

**Preview the migration SQL (offline, no DB required):**

```bash
uv run alembic upgrade head --sql
```

Read the output.  Confirm it contains only `CREATE TABLE`, `CREATE INDEX` or
`ALTER TABLE ADD COLUMN` statements.

**Apply migrations to the configured Supabase database:**

```bash
uv run alembic upgrade head
```

**Verify:**

```bash
uv run alembic current   # should print the latest revision hash
```

---

## 6. Database: seed initial data

```bash
# Seed the NIFTY 200 universe identity record.
uv run python jobs/seed_universe.py

# Import the current NIFTY 200 constituent list from the official Nifty source.
uv run python jobs/import_nifty200.py
```

Both jobs are idempotent — running them twice creates no duplicate records.

**Verify (expected output from first run):**

```
Universe identity seeded
200 securities imported, 0 updated
```

---

## 7. Ingest market data

```bash
# Download and persist daily OHLCV for all 200 NIFTY 200 members.
# Default start: 2015-01-01 (override with --start YYYY-MM-DD).
# Snapshots are written to data/snapshots/<run_id>/.
uv run python jobs/ingest_prices.py
```

The job is incremental: a second run fetches only the seven-day overlap window.

For a single-symbol recovery:

```bash
uv run python jobs/ingest_prices.py --symbols RELIANCE
```

---

## 8. Run scheduled jobs

```bash
# Layer 1: sector-divergence calculation
uv run python jobs/calculate_sector_divergence.py

# Layer 2: correlation MST calculation
uv run python jobs/calculate_mst.py
```

Each job writes its run metadata and results to the database and prints a
structured summary.

---

## 9. Start the API server

```bash
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
# Expected: {"status":"ok","database":"connected"}
```

---

## 10. Start the frontend dev server

```bash
cd frontend
pnpm install        # only needed once, or after pnpm-lock.yaml changes
pnpm dev
```

Open <http://localhost:5173> in a browser.  The dev server proxies `/api/*` to
the FastAPI server at port 8000.

---

## 11. Run tests and linters

All tests run without a real database connection (SQLite in-memory or pure
mocks):

```bash
# From the repository root:
uv run ruff check .
uv run mypy backend jobs
uv run pytest -ra --tb=short

# From the frontend/ directory:
pnpm lint
pnpm test
pnpm build
```

CI runs the same commands via `.github/workflows/ci.yml`.

---

## 12. Restore from a Supabase backup

Supabase provides point-in-time recovery (PITR) and logical backups through the
dashboard.

### 12.1 Using the Supabase dashboard

1. Go to **Project → Database → Backups** in the Supabase dashboard.
2. Select the desired backup timestamp.
3. Click **Restore** and follow the prompts.
4. After restoration, verify connectivity and table row counts.

### 12.2 Using `pg_restore` (logical backup)

If you exported a logical dump with `pg_dump`:

```bash
# Export (replace with your actual connection details — never commit this):
pg_dump "$PRISM_DATABASE_URL" --format=custom --file=prism_backup.dump

# Restore to a fresh Supabase database:
pg_restore --dbname="$PRISM_DATABASE_URL" --no-owner prism_backup.dump
```

### 12.3 After any restore

```bash
# Re-run migrations to ensure the schema is at head.
uv run alembic upgrade head

# Verify tables and row counts.
uv run alembic current
```

> [!NOTE]
> Raw source CSV snapshots are stored in `data/snapshots/<run_id>/`.  These are
> **not** committed to Git.  Back them up separately if re-ingestion from the
> original provider is not possible.

---

## 13. Teammate sign-off checklist

A teammate (different from the author) should follow every step in this document
on a clean machine and sign off by ticking each item below.

```
[ ] Cloned the repository successfully.
[ ] Created .env from .env.example with correct values.
[ ] uv sync --dev completed with no errors.
[ ] uv run alembic upgrade head --sql reviewed (additive only).
[ ] uv run alembic upgrade head applied successfully.
[ ] uv run python jobs/seed_universe.py seeded without errors.
[ ] uv run python jobs/import_nifty200.py imported 200 securities.
[ ] uv run python jobs/ingest_prices.py completed (or partial with expected
    failures documented).
[ ] uv run python jobs/calculate_sector_divergence.py produced scores.
[ ] uv run python jobs/calculate_mst.py produced a connected acyclic graph.
[ ] uv run uvicorn ... started and /api/v1/health returned {"status":"ok"}.
[ ] pnpm dev started and http://localhost:5173 loaded the dashboard.
[ ] uv run ruff check . — All checks passed!
[ ] uv run mypy backend jobs — passed with 0 errors.
[ ] uv run pytest -ra — all tests passed.
[ ] pnpm lint — no lint errors.
[ ] pnpm test — all Vitest tests passed.
[ ] pnpm build — TypeScript/Vite build succeeded.
[ ] Supabase restore tested (or confirmed with Supabase PITR enabled).
```

**Signed off by:** _________________________  **Date:** _________

> [!WARNING]
> The SRS Section 16 item "Setup and recovery instructions have been tested by
> another team member" is marked **NOT DONE** until a teammate completes and
> signs the checklist above.
