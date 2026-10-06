# PRISM Data Sources and Refresh Procedure

The database-backed `data_source` registry and `GET /api/v1/data/sources` are the
runtime source of truth. This document explains how an operator refreshes those
sources without undocumented APIs, browser impersonation, or production fixtures.
PRISM stores only news metadata (headline, URL, source, timestamp, content hash),
never article text.

## Automated sources

| Dataset | Source and access | Cadence | Terms/source page | Current status |
|---|---|---:|---|---|
| Prices, benchmark, actions, fundamentals | Yahoo adapter | Daily/quarterly | [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) | Live prototype source; unofficial and not for redistribution |
| RBI policy news | [Official RBI press-release RSS](https://rbi.org.in/pressreleases_rss.xml) | Event-driven; polled every 30 minutes | [RBI RSS page](https://www.rbi.org.in/Scripts/rss.aspx) | Live; newest stored item at verification: 2026-10-06 09:00 UTC |
| SEBI policy news | [Official SEBI RSS](https://www.sebi.gov.in/sebirss.xml) | Event-driven; polled every 30 minutes | [SEBI RSS page](https://www.sebi.gov.in/rss.html) | Live; newest stored item at verification: 2026-10-04 18:30 UTC |
| PIB policy news | PIB RSS listing | Event-driven | [PIB RSS page](https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=48) | TBD: identified application request returned HTTP 403 and items lacked a usable timestamp |
| Ministry of Finance | PIB releases | Daily | [PIB releases](https://www.pib.gov.in/AllRelease.aspx) | TBD: no separate permitted, current, timestamped feed verified |
| Crude oil, USD/INR, India 10Y, India VIX | Yahoo tickers registered individually | Daily | [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) | Live prototype sources; source limitations remain visible |
| FII/DII net flows | Official export required | Daily | [NSE terms](https://www.nseindia.com/static/nse-terms-of-use) | TBD |

Refresh verified RSS metadata:

```powershell
uv run python jobs/ingest_news.py
uv run python jobs/match_policy.py
uv run python jobs/calculate_news_impact.py
```

The RSS job fails if every enabled feed fails. A feed that returns no complete,
timestamped item is not recorded as successful.

## Manual official NSE exports

[NSE terms](https://www.nseindia.com/static/nse-terms-of-use) prohibit systematic
or automated collection. These paths therefore require a human download from the
official site. Do not automate the pages, spoof browser headers, or redistribute
the files.

### Corporate announcements

1. Open the [NSE corporate announcements page](https://www.nseindia.com/companies-listing/corporate-filings-announcements).
2. Select the required date range and download the CSV using the page's download control.
3. Place it at `data/raw/announcements/nse_announcements.csv`.
4. Confirm the export contains symbol, company name, subject, and broadcast date/time. The importer accepts the official uppercase headers and rejects unreadable rows before writing.
5. Run:

```powershell
uv run python jobs/ingest_announcements.py --source-file data/raw/announcements/nse_announcements.csv --dry-run
uv run python jobs/ingest_announcements.py --source-file data/raw/announcements/nse_announcements.csv
```

### Shareholding and total shares

1. Open the [NSE shareholding-pattern page](https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern).
2. Download the official CSV/XBRL or Excel disclosure for the required quarter.
3. Preserve the original file. Export a normalized CSV at `data/raw/shareholding/nse_shareholding.csv` with these exact columns:
   `symbol,quarter_end,promoter_pct,promoter_pledged_pct_of_promoter,fii_pct,dii_pct,public_pct,published_at,shares_outstanding,source_doc_id`.
4. Copy values only from the official disclosure. `published_at` is the actual exchange publication time; `quarter_end` must be 31 March, 30 June, 30 September, or 31 December; percentages must be in 0–100; total shares must be a positive whole number. If the export does not disclose a field, leave it empty—never infer it.
5. Run:

```powershell
uv run python jobs/ingest_shareholding.py --file data/raw/shareholding/nse_shareholding.csv
uv run python jobs/derive_market_stats.py
```

Exact re-imports are idempotent. A changed disclosure is retained as a new version.
`security_share_count` is populated only when the official row supplies
`shares_outstanding`. No real shareholding file was supplied during Step 11b, so
production shareholding and total-share loading remain pending/TBD.

### Insider trades

1. Open the [NSE insider-trading archive](https://www.nseindia.com/companies-listing/corporate-filings-insider-trading-archive-data).
2. Download the official CSV/XBRL using the page control.
3. Preserve the original. Export a normalized CSV at `data/raw/insider_trades/nse_insider_trades.csv` with these exact columns:
   `symbol,person_category,txn_type,quantity,value,txn_date,published_at,source_doc_id`.
4. Map the disclosed transaction to `buy`, `sell`, `pledge`, or `revoke_pledge` without inference. Keep actual publication time and INR value.
5. Run:

```powershell
uv run python jobs/ingest_insider_trades.py --file data/raw/insider_trades/nse_insider_trades.csv
```

Missing files, missing columns, invalid units, impossible percentages, invalid
quarter ends, negative quantities/values, and unreadable rows abort the import.

### FII/DII net flows

The importer can accept a user-supplied official daily or monthly export only after
it is normalized to `data/raw/macro/fii_dii_net_flows.csv` with these exact columns:
`date,value,published_at,version`. `value` is the combined FII/DII net flow in INR
crores for that observation period; `published_at` must be the actual publication
timestamp with a timezone; `version` starts at `1`. Do not infer a publication time
or expand one daily row into a monthly history.

Run the strict import with:

```powershell
uv run python jobs/ingest_macro.py --source csv --series fii_dii_net_flows --file data/raw/macro/fii_dii_net_flows.csv
```

## Freshness and source status

Cadence and grace are versioned in approved `model_config` key
`data_source_policy:1.0.0`; the table mirrors the human-readable cadence. The
freshness evaluator classifies never-successful registered sources as `missing` and
successful sources as `fresh` or `stale`. Stale component inputs already reduce the
component-weighted `data_freshness` confidence factor.

ASSUMPTION: daily market/manual sources use a two-calendar-day grace to tolerate
weekends and holidays; quarterly disclosures use a 45-day grace. These operational
defaults are proposed in PD-28 and are not regulatory deadlines.

## Monthly checklist

- Review `/data-health`; resolve every `stale`, `missing`, and `TBD` source.
- Re-run RSS ingestion and confirm both RBI and SEBI show a recent success.
- Download official announcement, shareholding, and insider exports according to their cadence.
- Run each importer first with validation/dry-run where available; archive original files privately.
- Run `jobs/derive_market_stats.py` after a real share-count import.
- Run `jobs/evaluate_alerts.py` and confirm stale inputs are visible in confidence and UI.
- Review source terms and access status; disable a source immediately if its terms or format changes.
- Never commit raw licensed exports, `.env`, credentials, or article bodies.
