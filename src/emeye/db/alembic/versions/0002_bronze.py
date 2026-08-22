# SPDX-License-Identifier: AGPL-3.0-or-later
"""bronze tables

Adds raw_document (immutable landing zone) and ingest_run (execution history),
plus a trigger enforcing that raw_document is append-only.

Revision ID: 0002
Revises: 0001
Created: 2026-08-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Bronze is append-only, and that is enforced here rather than left to reviewer
# discipline. Every parse in this project is replayable from these rows; an
# UPDATE that "fixes" a payload destroys the evidence of what was actually
# served, and chart snapshots cannot be re-fetched.
#
# If a future migration genuinely needs to rewrite bronze, drop the trigger
# deliberately inside that migration and recreate it afterwards. Making that a
# visible, reviewable act is the entire point.
_GUARD_FUNCTION = """
create or replace function emeye_raw_document_append_only()
returns trigger
language plpgsql
as $$
begin
    raise exception
        'raw_document is append-only: % rejected. Bronze is the replay source '
        'for every parser, and chart snapshots cannot be re-fetched. If a '
        'migration must rewrite it, drop this trigger explicitly in that '
        'migration.', tg_op
        using errcode = 'restrict_violation';
end;
$$;
"""

_GUARD_TRIGGER = """
create trigger raw_document_append_only
before update or delete on raw_document
for each row
execute function emeye_raw_document_append_only();
"""


def upgrade() -> None:
    op.create_table(
        "raw_document",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.SmallInteger(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_body", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "endpoint",
            "params_hash",
            "fetched_at",
            name="uq_raw_document_request",
        ),
    )
    op.create_index(
        "ix_raw_document_latest",
        "raw_document",
        ["source", "endpoint", "fetched_at"],
        unique=False,
    )
    # Not unique: identical content on two days is two facts, and collapsing
    # them would destroy the chart time series.
    op.create_index(
        "ix_raw_document_content_hash",
        "raw_document",
        ["content_hash"],
        unique=False,
    )

    op.create_table(
        "ingest_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_fetched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_hits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_misses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_type", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingest_run_recent",
        "ingest_run",
        ["source", "started_at"],
        unique=False,
    )

    op.execute(_GUARD_FUNCTION)
    op.execute(_GUARD_TRIGGER)


def downgrade() -> None:
    op.execute("drop trigger if exists raw_document_append_only on raw_document")
    op.execute("drop function if exists emeye_raw_document_append_only()")

    op.drop_index("ix_ingest_run_recent", table_name="ingest_run")
    op.drop_table("ingest_run")

    op.drop_index("ix_raw_document_content_hash", table_name="raw_document")
    op.drop_index("ix_raw_document_latest", table_name="raw_document")
    op.drop_table("raw_document")
