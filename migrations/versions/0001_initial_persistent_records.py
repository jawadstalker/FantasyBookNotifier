"""Create subscriptions, scraping jobs and email delivery records."""
from alembic import op
import sqlalchemy as sa

revision = "0001_persistent_records"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("publishers", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subscriptions_email", "subscriptions", ["email"], unique=True)

    op.create_table(
        "scraping_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("publishers", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scraping_jobs_email", "scraping_jobs", ["email"], unique=False)
    op.create_index("ix_scraping_jobs_status", "scraping_jobs", ["status"], unique=False)

    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("recipient", sa.String(length=254), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_email_deliveries_idempotency_key", "email_deliveries", ["idempotency_key"], unique=True)
    op.create_index("ix_email_deliveries_recipient", "email_deliveries", ["recipient"], unique=False)
    op.create_index("ix_email_deliveries_status", "email_deliveries", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_email_deliveries_status", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_recipient", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_idempotency_key", table_name="email_deliveries")
    op.drop_table("email_deliveries")
    op.drop_index("ix_scraping_jobs_status", table_name="scraping_jobs")
    op.drop_index("ix_scraping_jobs_email", table_name="scraping_jobs")
    op.drop_table("scraping_jobs")
    op.drop_index("ix_subscriptions_email", table_name="subscriptions")
    op.drop_table("subscriptions")
