"""Alembic migration: add query_history table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "0002"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "query_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("is_grounded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("model_used", sa.String(128), nullable=False, server_default=""),
        sa.Column("usage_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("citations_json", JSON, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_query_history_created_at", "query_history", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_query_history_created_at", table_name="query_history")
    op.drop_table("query_history")
