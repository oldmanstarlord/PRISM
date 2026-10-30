# Presentation login

Flow: home → Explore → Sign in → My portfolio. Signed-in users skip the login form.
The login screen has email, password and Sign in. Log out is in the top bar and portfolio header.

## Supabase Auth (local and Render)

Add these credentials to the root `.env`:

```dotenv
PRISM_SUPABASE_URL=https://PROJECT_REF.supabase.co
PRISM_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
PRISM_SUPABASE_SECRET_KEY=YOUR_SERVER_ONLY_SECRET_KEY
```

Then run this once from the repository root (Node 24 and installed frontend dependencies):

```powershell
node --env-file=.env jobs/provision_supabase_accounts.mjs
```

The script creates three confirmed Supabase email/password users, verifies their sign-ins,
and links existing local portfolios, transactions and journals to the real Supabase user IDs.
If there is no saved local portfolio, it creates the initial portfolio. Re-running preserves
existing accounts, passwords and portfolio edits. If both identities already have portfolios,
it stops for review instead of merging them. The initial password is `Prism@2026`; override
it with `PRISM_PRESENTATION_PASSWORD` before provisioning if needed.

Only after all accounts are linked does the script configure the frontend public URL/key
and disable local authentication. The secret key is used only by the setup script; it never
enters frontend configuration or the Docker build. Restart your own local processes afterward.

On Render, set the matching `PRISM_SUPABASE_URL`, `PRISM_SUPABASE_PUBLISHABLE_KEY`,
`VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` values. Keep
`PRISM_LOCAL_AUTH_ENABLED=false` and `VITE_LOCAL_AUTH_ENABLED=false`, then rebuild/deploy.
Do not add the administrative secret key to Render: ordinary login uses only the public key
and the signed-in user's access token. Provisioning is a separate, one-time operation.

The existing seed fixtures are preserved; their market analytics coverage depends on the
published stock metrics and MST universe. Authentication provisioning does not replace holdings.

## Optional local-only authentication

To deliberately use the older local presentation setup instead, use these environment files:

```dotenv
# .env
PRISM_LOCAL_AUTH_ENABLED=true
PRISM_ENVIRONMENT=development

# frontend/.env
VITE_LOCAL_AUTH_ENABLED=true
```

Restart your own frontend and backend processes after changing environment settings.
The existing PostgreSQL database must be available and migrated.

Accounts (shared initial password: `Prism@2026`):

- `aarav@prism.com`: HDFCBANK, ITC, HINDUNILVR, TCS, SUNPHARMA.
- `priya@prism.com`: RELIANCE, INFY, ICICIBANK, LT, MARUTI.
- `rohan@prism.com`: TATAMOTORS, BAJFINANCE, ADANIENT, TATASTEEL, BEL.

The first successful login creates that account's portfolio and purchase transactions.
Later logins preserve the saved portfolio and subsequent changes. Browser holdings and
journal caches are scoped to the account; existing anonymous caches are not imported.
Seed purchases are presentation sample data, not actual investment performance.

Set `PRISM_LOCAL_ACCOUNT_PASSWORD` in the backend environment to override the shared
password. Sessions expire after eight hours. Without `PRISM_LOCAL_AUTH_SECRET`, restarting
the backend invalidates existing sessions; sign in again. Set a long random secret in the
backend environment if sessions must survive restarts.

Local account authentication only works in development with local auth explicitly enabled.
Requests to protected endpoints still require a valid bearer token. For a Supabase deployment,
set `VITE_LOCAL_AUTH_ENABLED=false` and configure Supabase in both environments.
