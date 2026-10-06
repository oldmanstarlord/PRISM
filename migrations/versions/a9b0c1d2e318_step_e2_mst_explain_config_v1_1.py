"""Add complete draft MST explanation wording as a new config version.

Revision ID: a9b0c1d2e318
Revises: f8a9b0c1d217
Create Date: 2026-10-06
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.versions.f8a9b0c1d217_step_e2_mst_explain_config import CONFIG as BASE_CONFIG

revision = "a9b0c1d2e318"
down_revision = "f8a9b0c1d217"
branch_labels = None
depends_on = None

CONFIG = copy.deepcopy(BASE_CONFIG)
templates = CONFIG["templates"]
assert isinstance(templates, dict)
templates.update(
    {
        "macro": (
            "The industries' significant macro sensitivity vectors had similarity "
            "{macro_similarity}; their strongest shared stored driver was {macro_driver}."
        ),
        "cooccurring": (
            "The last 90 days contained {cooccurring_items} stored co-occurring event or "
            "news items for the pair."
        ),
        "cluster_portfolio": (
            "The pair's stored cluster represented {cluster_risk}% of portfolio risk "
            "contribution in the loaded portfolio run."
        ),
        "cluster_peers": "Its stored cluster peers are {cluster_peers}.",
    }
)
CONFIG["approval_note"] = (
    "Draft complete Step E2 wording; owner review is required before approval."
)


def upgrade() -> None:
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
    canonical = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
    now = datetime.now(UTC)
    row = {
        "id": uuid4(),
        "config_key": "mst_explain_templates",
        "version": "1.1.0",
        "status": "draft",
        "configuration": CONFIG,
        "configuration_hash": hashlib.sha256(canonical.encode()).hexdigest(),
        "created_at": now,
        "updated_at": now,
    }
    if getattr(op.get_context(), "as_sql", False):
        config_json = canonical.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, configuration_hash, "
            "created_at, updated_at) "
            f"VALUES ('{row['id']}', 'mst_explain_templates', '1.1.0', 'draft', "
            f"'{config_json}'::jsonb, '{row['configuration_hash']}', "
            f"'{row['created_at'].isoformat()}', '{row['updated_at'].isoformat()}')"
        )
    else:
        op.bulk_insert(table, [row])


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_config WHERE config_key='mst_explain_templates' AND version='1.1.0'"
    )
