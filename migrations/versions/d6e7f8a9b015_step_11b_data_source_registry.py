"""Add the Step 11b permitted-source registry.

Revision ID: d6e7f8a9b015
Revises: c5d6e7f8a914
Create Date: 2026-10-06
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d6e7f8a9b015"
down_revision = "c5d6e7f8a914"
branch_labels = None
depends_on = None

SOURCE_POLICY: dict[str, object] = {
    "sources": {
        "universe_nifty200": {"expected_cadence_minutes": 43200, "grace_minutes": 10080},
        "prices_yahoo": {"expected_cadence_minutes": 1440, "grace_minutes": 2880},
        "benchmark_yahoo": {"expected_cadence_minutes": 1440, "grace_minutes": 2880},
        "corporate_actions_yahoo": {
            "expected_cadence_minutes": 1440,
            "grace_minutes": 2880,
        },
        "fundamentals_yahoo": {"expected_cadence_minutes": 129600, "grace_minutes": 64800},
        "announcements_nse_manual": {
            "expected_cadence_minutes": 1440,
            "grace_minutes": 2880,
        },
        "shareholding_nse_manual": {
            "expected_cadence_minutes": 129600,
            "grace_minutes": 64800,
        },
        "insider_trades_nse_manual": {
            "expected_cadence_minutes": 1440,
            "grace_minutes": 2880,
        },
        "shares_outstanding_nse_manual": {
            "expected_cadence_minutes": 129600,
            "grace_minutes": 64800,
        },
        "news_rbi_rss": {"expected_cadence_minutes": 30, "grace_minutes": 1440},
        "news_sebi_rss": {"expected_cadence_minutes": 30, "grace_minutes": 1440},
        "news_pib_rss": {"expected_cadence_minutes": 30, "grace_minutes": 1440},
        "policy_finance_ministry": {"expected_cadence_minutes": 1440, "grace_minutes": 2880},
        "macro_crude_oil_yahoo": {"expected_cadence_minutes": 1440, "grace_minutes": 2880},
        "macro_usd_inr_yahoo": {"expected_cadence_minutes": 1440, "grace_minutes": 2880},
        "macro_in_10y_yield_yahoo": {
            "expected_cadence_minutes": 1440,
            "grace_minutes": 2880,
        },
        "macro_india_vix_yahoo": {"expected_cadence_minutes": 1440, "grace_minutes": 2880},
        "macro_fii_dii_manual": {"expected_cadence_minutes": 1440, "grace_minutes": 2880},
    },
    "assumptions": [
        "Daily market sources allow a two-calendar-day grace for weekends and holidays.",
        "Quarterly disclosures allow a 45-day grace after their expected cadence.",
    ],
}

SOURCES: list[dict[str, object]] = [
    {
        "source_key": "universe_nifty200",
        "dataset": "universe",
        "owner": "NSE Indices Limited",
        "access_method": "file_download",
        "terms_url": "https://www.niftyindices.com/reports/index-watch",
        "license_note": (
            "Official constituent download; review NSE Indices terms before redistribution."
        ),
        "cadence": "monthly",
        "expected_grace_days": 7,
        "status": "live",
        "notes": "Current membership only; historical survivorship limitation remains.",
    },
    {
        "source_key": "prices_yahoo",
        "dataset": "prices",
        "owner": "Yahoo",
        "access_method": "api",
        "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
        "license_note": (
            "Prototype research use; not an official exchange feed and not for redistribution."
        ),
        "cadence": "daily",
        "expected_grace_days": 2,
        "status": "live",
        "notes": "End-of-day prices only.",
    },
    {
        "source_key": "benchmark_yahoo",
        "dataset": "benchmark",
        "owner": "Yahoo",
        "access_method": "api",
        "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
        "license_note": "Single unofficial benchmark source for prototype research use.",
        "cadence": "daily",
        "expected_grace_days": 2,
        "status": "live",
        "notes": "NIFTY 200 price index ticker ^CNX200.",
    },
    {
        "source_key": "corporate_actions_yahoo",
        "dataset": "corporate_actions",
        "owner": "Yahoo",
        "access_method": "api",
        "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
        "license_note": (
            "Prototype research use; cross-check important actions against issuer filings."
        ),
        "cadence": "daily",
        "expected_grace_days": 2,
        "status": "live",
        "notes": "Replaceable adapter.",
    },
    {
        "source_key": "fundamentals_yahoo",
        "dataset": "fundamentals",
        "owner": "Yahoo",
        "access_method": "api",
        "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
        "license_note": "Prototype research use; publication timestamps remain source-dependent.",
        "cadence": "quarterly",
        "expected_grace_days": 45,
        "status": "live",
        "notes": "Components expose missing and stale statuses.",
    },
    {
        "source_key": "announcements_nse_manual",
        "dataset": "announcements",
        "owner": "National Stock Exchange of India Limited",
        "access_method": "manual_import",
        "terms_url": "https://www.nseindia.com/static/nse-terms-of-use",
        "license_note": (
            "Manual official CSV export only; no automated collection or redistribution."
        ),
        "cadence": "daily-manual",
        "expected_grace_days": 2,
        "status": "manual",
        "notes": "Strict normalized importer; operator downloads the official export.",
    },
    {
        "source_key": "shareholding_nse_manual",
        "dataset": "shareholding",
        "owner": "National Stock Exchange of India Limited",
        "access_method": "manual_import",
        "terms_url": "https://www.nseindia.com/static/nse-terms-of-use",
        "license_note": "Manual official disclosure export only; no automated collection.",
        "cadence": "quarterly-manual",
        "expected_grace_days": 45,
        "status": "manual",
        "notes": "No real file supplied yet; registry status remains manual until import.",
    },
    {
        "source_key": "insider_trades_nse_manual",
        "dataset": "insider_trades",
        "owner": "National Stock Exchange of India Limited",
        "access_method": "manual_import",
        "terms_url": "https://www.nseindia.com/static/nse-terms-of-use",
        "license_note": "Manual official disclosure export only; no automated collection.",
        "cadence": "daily-manual",
        "expected_grace_days": 2,
        "status": "manual",
        "notes": "No real file supplied yet; registry status remains manual until import.",
    },
    {
        "source_key": "shares_outstanding_nse_manual",
        "dataset": "shares_outstanding",
        "owner": "National Stock Exchange of India Limited",
        "access_method": "manual_import",
        "terms_url": "https://www.nseindia.com/static/nse-terms-of-use",
        "license_note": "Derived only from a supplied official shareholding disclosure export.",
        "cadence": "quarterly-manual",
        "expected_grace_days": 45,
        "status": "tbd",
        "notes": "TBD until a real export containing total shares is supplied and loaded.",
    },
    {
        "source_key": "news_rbi_rss",
        "dataset": "news_policy",
        "owner": "Reserve Bank of India",
        "access_method": "rss",
        "terms_url": "https://www.rbi.org.in/Scripts/rss.aspx",
        "license_note": "Headline, URL, timestamp and content hash only; no article body stored.",
        "cadence": "event-driven-polled-30m",
        "expected_grace_days": 1,
        "status": "live",
        "notes": "Official press-release RSS verified 2026-10-06.",
    },
    {
        "source_key": "news_sebi_rss",
        "dataset": "news_policy",
        "owner": "Securities and Exchange Board of India",
        "access_method": "rss",
        "terms_url": "https://www.sebi.gov.in/rss.html",
        "license_note": "Headline, URL, timestamp and content hash only; no article body stored.",
        "cadence": "event-driven-polled-30m",
        "expected_grace_days": 1,
        "status": "live",
        "notes": "Official RSS verified 2026-10-06.",
    },
    {
        "source_key": "news_pib_rss",
        "dataset": "news_policy",
        "owner": "Press Information Bureau, Government of India",
        "access_method": "rss",
        "terms_url": "https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=48",
        "license_note": (
            "Not enabled until an identified client receives current parseable items reliably."
        ),
        "cadence": "event-driven-polled-30m",
        "expected_grace_days": 1,
        "status": "tbd",
        "notes": (
            "TBD: verification returned HTTP 403 to the application client and no usable pubDate."
        ),
    },
    {
        "source_key": "policy_finance_ministry",
        "dataset": "news_policy",
        "owner": "Ministry of Finance, Government of India",
        "access_method": "rss",
        "terms_url": "https://www.pib.gov.in/AllRelease.aspx",
        "license_note": (
            "No separate permitted current feed verified; disabled from production ingestion."
        ),
        "cadence": "daily",
        "expected_grace_days": 2,
        "status": "tbd",
        "notes": "TBD pending a separately verified official feed or documented manual import.",
    },
    {
        "source_key": "macro_crude_oil_yahoo",
        "dataset": "macro:crude_oil",
        "owner": "Yahoo",
        "access_method": "api",
        "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
        "license_note": "Yahoo Finance BZ=F prototype research source.",
        "cadence": "daily",
        "expected_grace_days": 2,
        "status": "live",
        "notes": "End-of-day series.",
    },
    {
        "source_key": "macro_usd_inr_yahoo",
        "dataset": "macro:usd_inr",
        "owner": "Yahoo",
        "access_method": "api",
        "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
        "license_note": "Yahoo Finance INR=X prototype research source.",
        "cadence": "daily",
        "expected_grace_days": 2,
        "status": "live",
        "notes": "End-of-day series.",
    },
    {
        "source_key": "macro_in_10y_yield_yahoo",
        "dataset": "macro:in_10y_yield",
        "owner": "Yahoo",
        "access_method": "api",
        "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
        "license_note": "Yahoo Finance ^IN10YT=RR prototype research source.",
        "cadence": "daily",
        "expected_grace_days": 2,
        "status": "live",
        "notes": "Not a primary RBI/CCIL feed; expose this limitation.",
    },
    {
        "source_key": "macro_india_vix_yahoo",
        "dataset": "macro:india_vix",
        "owner": "Yahoo",
        "access_method": "api",
        "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
        "license_note": "Yahoo Finance ^INDIAVIX prototype research source.",
        "cadence": "daily",
        "expected_grace_days": 2,
        "status": "live",
        "notes": "Not an official NSE distribution feed.",
    },
    {
        "source_key": "macro_fii_dii_manual",
        "dataset": "macro:fii_dii_net_flows",
        "owner": "NSE/BSE/NSDL",
        "access_method": "manual_import",
        "terms_url": "https://www.nseindia.com/static/nse-terms-of-use",
        "license_note": "No permitted automated production source is configured.",
        "cadence": "daily-manual",
        "expected_grace_days": 2,
        "status": "tbd",
        "notes": "TBD pending a documented official export and strict importer.",
    },
]


def _insert_config() -> None:
    payload = json.dumps(SOURCE_POLICY, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.String()),
        sa.column("version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", postgresql.JSONB()),
        sa.column("configuration_hash", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    if getattr(op.get_context(), "as_sql", False):
        escaped = payload.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, configuration_hash, "
            "created_at, updated_at) "
            f"VALUES ('{uuid4()}', 'data_source_policy', '1.0.0', 'approved', "
            f"'{escaped}'::jsonb, '{fingerprint}', now(), now())"
        )
    else:
        now = datetime.now(UTC)
        op.bulk_insert(
            table,
            [
                {
                    "id": uuid4(),
                    "config_key": "data_source_policy",
                    "version": "1.0.0",
                    "status": "approved",
                    "configuration": SOURCE_POLICY,
                    "configuration_hash": fingerprint,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )


def upgrade() -> None:
    op.create_table(
        "data_source",
        sa.Column("source_key", sa.String(100), primary_key=True),
        sa.Column("dataset", sa.String(100), nullable=False),
        sa.Column("owner", sa.String(180), nullable=False),
        sa.Column("access_method", sa.String(30), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.Column("cadence", sa.String(50), nullable=False),
        sa.Column("expected_grace_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(
            "access_method IN ('api', 'rss', 'file_download', 'manual_import')",
            name="ck_data_source_access_method",
        ),
        sa.CheckConstraint(
            "status IN ('live', 'manual', 'tbd', 'disabled')",
            name="ck_data_source_status",
        ),
        sa.CheckConstraint("expected_grace_days >= 0", name="ck_data_source_grace_nonnegative"),
    )
    op.create_index("ix_data_source_dataset", "data_source", ["dataset"])
    op.create_index("ix_data_source_status", "data_source", ["status"])
    source_table = sa.table(
        "data_source",
        sa.column("source_key", sa.String()),
        sa.column("dataset", sa.String()),
        sa.column("owner", sa.String()),
        sa.column("access_method", sa.String()),
        sa.column("terms_url", sa.Text()),
        sa.column("license_note", sa.Text()),
        sa.column("cadence", sa.String()),
        sa.column("expected_grace_days", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("last_verified_at", sa.DateTime(timezone=True)),
        sa.column("last_success_at", sa.DateTime(timezone=True)),
        sa.column("notes", sa.Text()),
    )
    op.bulk_insert(source_table, SOURCES)
    _insert_config()


def downgrade() -> None:
    op.execute("DELETE FROM model_config WHERE config_key='data_source_policy' AND version='1.0.0'")
    op.drop_index("ix_data_source_status", table_name="data_source")
    op.drop_index("ix_data_source_dataset", table_name="data_source")
    op.drop_table("data_source")
