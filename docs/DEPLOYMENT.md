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

## Separate Vercel frontend and native Render backend

Deploy the same release to both services. A push to another repository or branch
does not update the repository and branch configured in Vercel or Render.

In Vercel, select `frontend` as the Root Directory, Vite as the framework, and `dist`
as the output directory. Configure these production environment variables and redeploy:

```text
VITE_API_URL=https://YOUR-BACKEND.onrender.com/api/v1
VITE_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_SUPABASE_KEY
```

`frontend/vercel.json` declares the Vite build and rewrites each React Router page
to `index.html`. This lets direct links and refreshes on `/portfolio`, `/news`,
`/mst`, `/portfolio-demo`, and `/companies/:symbol` load the app. Keep the Vercel
Root Directory set to `frontend` so Vercel reads this configuration. Add a matching
rewrite when adding a new browser route; assets and `/api/*` are not rewritten.
The API URL above must point to the Render backend.

After deploying, open a portfolio/company link directly in a new tab and refresh it.
Both requests must return the app HTML with HTTP 200, while the URL and company
query parameters remain intact. This setting follows Vercel's
[Vite SPA routing guidance](https://vercel.com/docs/frameworks/frontend/vite#using-vite-to-make-spas).

In the native Render Python service, use the repository root and configure:

```text
PRISM_CORS_ORIGINS=["https://YOUR-FRONTEND.vercel.app"]
PRISM_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
PRISM_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_SUPABASE_KEY
PRISM_NEWS_AUTO_REFRESH=true
HF_HOME=/opt/render/project/src/data/huggingface
```

Keep `PRISM_DATABASE_URL` and `PRISM_FIRECRAWL_API_KEY` configured on Render.
Both services must use the same Supabase project. In Supabase Authentication's URL
Configuration, set the Site URL and allowed redirect URLs to the frontend HTTPS URL.
Users can then use **Sign in** in the app header for account sync and protected
portfolio news analysis; guests can still use local holdings and public research.

For news sentiment, the pinned FinBERT weights must be downloaded during the build.
Setting `HF_HOME` alone does not download them. Use this Render Build Command:

```sh
uv sync --locked --no-dev && uv run --no-sync python -m jobs.setup_news_model
```

Successful build logs include `FinBERT cached at` and two sentiment inference results.
Run database migrations with `uv run --no-sync alembic upgrade head` before starting
a new release. Use this Start Command:

```sh
uv run --no-sync uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

The API scheduler starts news collection when auto-refresh is enabled and the model
is ready; a separate background `jobs.collect_news` start command is unnecessary.
Check `/api/v1/news`: `status.model_ready` must be `true`, and then check
`last_success_at`, `error`, and `warnings` for collection results. HTTP 200 alone
does not mean news collection succeeded. If inference is killed for insufficient
memory, increase the service's memory; do not bypass sentiment setup or authentication.
Files created at runtime on a service without a persistent disk are lost on redeploy.

Yahoo `Invalid Crumb`/`Unauthorized` messages describe an upstream quote-provider
failure, separate from PRISM authentication and FinBERT setup. A successful PRISM
quotes response can contain a fallback: check its freshness/source metadata before
presenting it as live data.

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
