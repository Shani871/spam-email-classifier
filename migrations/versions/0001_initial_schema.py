"""Initial schema: history, feedback, sender rules and deleted accounts.

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assessment", sa.String(40), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(40), nullable=False),
    )
    op.create_index("ix_history_account_created", "history", ["account_id", "created_at"])
    op.create_index("ix_history_expires_at", "history", ["expires_at"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("predicted_label", sa.String(16), nullable=False, server_default=""),
        sa.Column("user_label", sa.String(8), nullable=False),
        sa.Column("user_comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("consent_given", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("user_label IN ('ham', 'spam')", name="ck_feedback_user_label"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'withdrawn')", name="ck_feedback_status"),
    )
    op.create_index("ix_feedback_account_created", "feedback", ["account_id", "created_at"])
    op.create_index("ix_feedback_review", "feedback", ["consent_given", "status", "expires_at"])

    op.create_table(
        "sender_rules",
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("address", sa.String(320), primary_key=True),
        sa.Column("rule", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rule IN ('trust', 'block')", name="ck_sender_rules_rule"),
    )

    op.create_table(
        "deleted_accounts",
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("deleted_accounts")
    op.drop_table("sender_rules")
    op.drop_index("ix_feedback_review", table_name="feedback")
    op.drop_index("ix_feedback_account_created", table_name="feedback")
    op.drop_table("feedback")
    op.drop_index("ix_history_expires_at", table_name="history")
    op.drop_index("ix_history_account_created", table_name="history")
    op.drop_table("history")
