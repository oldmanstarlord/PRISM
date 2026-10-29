# PRISM

Portfolio Risk & Intelligence System for Markets. React/TypeScript UI, FastAPI API,
PostgreSQL storage, and Supabase authentication. Research software; not investment advice.

## Run locally

Requires Python 3.12, Node 24, pnpm 10.16.1 and a PostgreSQL/Supabase project.

1. Copy `.env.example` to `.env` and `frontend/.env.example` to `frontend/.env`.
2. Fill in the database URL and matching Supabase URL/publishable key in both files.
3. Run `./run.sh`. The UI runs at http://localhost:5173 and API at http://localhost:8000.

Never commit `.env` files. Publishable Supabase keys are public browser configuration;
service-role keys and database passwords must stay server-side.

## Deploy

See [deployment instructions](docs/DEPLOYMENT.md) for Render and Docker Compose.
The production image builds the UI and serves it alongside the API on one origin.

After configuring `.env`, start the complete container deployment with:

```sh
docker compose up --build -d --wait
```

Open http://localhost:8080. Compose runs database migrations before starting PRISM.
PostgreSQL and Supabase authentication are external services configured in `.env`.

## Checks

```sh
uv sync --locked --all-groups
uv run ruff check backend jobs tests deploy
uv run mypy backend jobs deploy
uv run pytest -m 'not integration'
uv run python -m jobs.check_repository_policy
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend lint
pnpm --dir frontend test
pnpm --dir frontend build
pnpm --dir frontend test:e2e
```

Database integration tests require a migrated test database and `PRISM_RUN_DB_INTEGRATION=1`.
Never point tests at a production database.

## Documentation

- [Deployment](docs/DEPLOYMENT.md): production setup and release checks.
- [Operations](OPERATIONS.md): ingestion, scheduled jobs, and model workflows.
- [Methodology](docs/METHODOLOGY.md): analytical methods and limitations.
- [Feature matrix](docs/FEATURE_MATRIX.md).
- [Fundamentals](FUNDAMENTALS.md).
- [Portfolio contract](PHASE1_PORTFOLIO_CONTRACT.md) and
  [analytics contract](PORTFOLIO_ANALYTICS_CONTRACT.md).
- [Temporal heterogeneous GNN](docs/TEMPORAL_HETERO_GNN.md).
