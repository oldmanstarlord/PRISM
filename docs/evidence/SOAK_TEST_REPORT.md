# Step 14 seven-day soak report

Status: **NOT STARTED — BLOCKED** as of 2026-10-06.

The scheduler and evidence-producing `pipeline_run` manifests are implemented, but
the production database contains quarantined fixture-derived announcement/news/macro
rows. Starting the daily score/alert DAG would mix those rows into operational
evidence. No soak result is invented.

After the owner authorizes cleanup with `APPROVE CLEANUP`, start:

```powershell
uv run python -m jobs.run_scheduler --soak-days 7
```

After seven elapsed days record: uptime, scheduled/finished/failed counts per task,
retry counts, freshness status durations, alert counts/dedup suppressions,
incremental child runs, last-known-good checks, and all unexpected exceptions.
