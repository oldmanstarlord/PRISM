## Shared portfolio deployment (current)

The app opens without authentication. All visitors use and can edit Aarav's shared
portfolio. The API resolves its owner from the existing portfolio named
`Aarav's Portfolio`, preserving its transactions and expanded holdings. If absent,
the portfolio screen seeds his original HDFCBANK, ITC, HINDUNILVR, TCS and SUNPHARMA
holdings under the fixed presentation owner. Existing portfolios are never reseeded.

Vercel needs only `VITE_API_URL=https://YOUR-BACKEND.onrender.com/api/v1`.
Render needs `PRISM_DATABASE_URL`, `PRISM_ENVIRONMENT=production`, and
`PRISM_CORS_ORIGINS=["https://YOUR-FRONTEND.vercel.app"]`.
`PRISM_FIRECRAWL_API_KEY` is optional. Supabase Auth keys are no longer required.
Keep the existing PostgreSQL database: portfolio data still lives there.

The older authentication deployment instructions below describe the previous release.

# Deployment

## Render

1. Push this repository to GitHub and create a Render **Blueprint**, selecting
   `render.yaml` from the branch you want to deploy.
2. Supply the prompted environment variables:
   - `PRISM_DATABASE_URL`: PostgreSQL URL with SSL. Use a Supabase session pooler
     or a directly reachable database; transaction poolers are unsuitable for migrations.
   - `PRISM_MIGRATION_DATABASE_URL`: direct/session-pooler URL for Alembic;
     leave empty to reuse the application database URL.
   - `PRISM_SUPABASE_URL` and `PRISM_SUPABASE_PUBLISHABLE_KEY`: authentication configuration.
   - `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`: the same public values
     for the browser build. Never use a service-role key here.
   - `PRISM_FIRECRAWL_API_KEY`: optional; leave empty if not using Firecrawl news collection.
3. Deploy. Render builds the multi-stage Docker image, runs `alembic upgrade head`,
   then checks `/api/v1/ready`. The container listens on Render's `PORT`.
4. In Supabase Authentication, set the Site URL and allowed redirect URLs to your
   Render HTTPS URL. Test sign-in, refresh, portfolio save and logout.

For the three presentation accounts and their existing portfolios, follow
[Supabase account provisioning](PRESENTATION_LOGIN.md#supabase-auth-local-and-render)
once before presenting. Local fixed accounts are not automatically Supabase users.
Keep `VITE_LOCAL_AUTH_ENABLED=false` for the production frontend build. The server-only
administrative key used for provisioning is not needed by Render or the browser.

The service uses one paid Standard instance and a 10 GB persistent disk. Review Render's
current pricing before creating it. Machine learning dependencies and inference are
memory intensive; monitor usage and increase resources if your selected models need more.
The first build downloads large Python/Torch packages and can take several minutes.
Models, news caches and downloaded artifacts persist under `/app/data`; model training
and market-data ingestion remain operational tasks, not part of an image build.

The default Render hostname automatically configures trusted hosts and CORS. For a custom
domain, explicitly set both `PRISM_TRUSTED_HOSTS` (JSON host list, including localhost
for health checks) and `PRISM_CORS_ORIGINS` (JSON HTTPS origin list). Add the custom
URL in Supabase too. Keep only one instance/worker because schedulers and rate limits
are process-local and caches are on a single disk. Persistent disks prevent zero-downtime
deploys; allow for a restart window.

## Docker Compose

Requires Docker Engine/Desktop with Compose v2 and an external PostgreSQL/Supabase project.

```sh
cp deploy/compose.env.example .env
# Edit .env with your database and Supabase credentials.
docker compose up --build -d --wait
```

If `.env` already exists, merge the template values into it instead of overwriting it.
Open http://localhost:8080. The database is deliberately external: the same deployment
can use Supabase on Render or your own managed PostgreSQL service. The `migrate` service
must complete successfully before `app` starts. Local browser requests use the same
origin and need no localhost CORS exception in production mode.

For public hosting, put a TLS reverse proxy in front of port 8080, set your HTTPS CORS
origin and trusted hostname, and restrict the public port to that proxy. Only trust
forwarded headers from your actual proxy via Uvicorn's `FORWARDED_ALLOW_IPS` if needed.

```sh
docker compose ps
docker compose logs --tail=100 app migrate
curl --fail http://localhost:8080/api/v1/ready
docker compose down
```

`down` preserves the named data volume. Do not use `down -v` unless intentionally
removing cached data/models. Back up PostgreSQL and the volume before upgrades.

## Release and rollback

Run the README checks before release. Verify the database connection, readiness,
Supabase login/logout, portfolio persistence and the startup animation against the
actual deployment. Build-time `VITE_*` changes require rebuilding the image.

Back up the database before migrations. Roll back application code/image to the
previous known-good commit only after checking schema compatibility; migrations may
require a separate reviewed database recovery plan. Keep secrets in Render's environment
settings or a local untracked `.env`, never Docker build arguments or Git.

Reference: [Render Docker](https://render.com/docs/docker) and
[Blueprint specification](https://render.com/docs/blueprint-spec).
