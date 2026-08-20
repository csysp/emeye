# SPDX-License-Identifier: AGPL-3.0-or-later
"""initial schema_meta

Proves the migration loop end to end — generate, apply, roll back — before any
real table depends on it. Bronze arrives in phase 2.

Revision ID: 0001
Revises:
Created: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schema_meta",
        sa.Column("key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("value", sa.String(length=512), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "insert into schema_meta (key, value) "
            "values ('schema_initialized_at', now()::text)"
        )
    )


def downgrade() -> None:
    op.drop_table("schema_meta")
