"""Correct correlation wording in MST explanation templates.

Revision ID: b0c1d2e3f419
Revises: a9b0c1d2e318
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

from migrations.versions.a9b0c1d2e318_step_e2_mst_explain_config_v1_1 import (
    CONFIG as BASE_CONFIG,
)

revision = "b0c1d2e3f419"
down_revision = "a9b0c1d2e318"
branch_labels = None
depends_on = None

CONFIG = copy.deepcopy(BASE_CONFIG)
templates = CONFIG["templates"]
assert isinstance(templates, dict)
templates["rolling_range"] = (
    "Across available stored windows, the pair's moves-together value ranged from "
    "{minimum} to {maximum}, with median {median}."
)
templates["path"] = (
    "The stored tree path has {hop_count} links: {path}; its weakest link has "
    "co-movement coefficient {weakest_correlation}."
)
CONFIG["limitations"] = [
    "MST links show statistical co-movement, not proof of a business relationship.",
    "The tree retains only N-1 links and omits many valid pairwise co-movements.",
    "Historical beta, co-movement and stability do not establish future effects.",
]
CONFIG["approval_note"] = (
    "Draft Step E2 wording with enforced correlation language; owner review is required."
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
        "version": "1.2.0",
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
            f"VALUES ('{row['id']}', 'mst_explain_templates', '1.2.0', 'draft', "
            f"'{config_json}'::jsonb, '{row['configuration_hash']}', "
            f"'{row['created_at'].isoformat()}', '{row['updated_at'].isoformat()}')"
        )
    else:
        op.bulk_insert(table, [row])


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_config WHERE config_key='mst_explain_templates' AND version='1.2.0'"
    )
