"""Create subscriptions, scraping jobs and email delivery records."""
from alembic import op
import sqlalchemy as sa

revision = "0001_persistent_records"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(name):
    return name in sa.inspect(op.get_bind()).get_table_names()


def _index_exists(table, name):
    if not _table_exists(table):
        return False
    return any(index["name"] == name for index in sa.inspect(op.get_bind()).get_indexes(table))


def _ensure_index(table, name, columns, unique=False):
    if not _index_exists(table, name):
        op.create_index(name, table, columns, unique=unique)


def upgrade():
    # Existing installations may already have these tables from create_all().
    # Check before creating so they can adopt Alembic without losing their data.
    if not _table_exists("subscriptions"):
        op.create_table(
            "subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(length=254), nullable=False),
            sa.Column("publishers", sa.JSON(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    _ensure_index("subscriptions", "ix_subscriptions_email", ["email"], unique=True)

    if not _table_exists("scraping_jobs"):
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
    _ensure_index("scraping_jobs", "ix_scraping_jobs_email", ["email"])
    _ensure_index("scraping_jobs", "ix_scraping_jobs_status", ["status"])

    if not _table_exists("email_deliveries"):
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
    _ensure_index("email_deliveries", "ix_email_deliveries_idempotency_key", ["idempotency_key"], unique=True)
    _ensure_index("email_deliveries", "ix_email_deliveries_recipient", ["recipient"])
    _ensure_index("email_deliveries", "ix_email_deliveries_status", ["status"])


def downgrade():
    for table, index in [
        ("email_deliveries", "ix_email_deliveries_status"),
        ("email_deliveries", "ix_email_deliveries_recipient"),
        ("email_deliveries", "ix_email_deliveries_idempotency_key"),
        ("scraping_jobs", "ix_scraping_jobs_status"),
        ("scraping_jobs", "ix_scraping_jobs_email"),
        ("subscriptions", "ix_subscriptions_email"),
    ]:
        if _index_exists(table, index):
            op.drop_index(index, table_name=table)
    for table in ("email_deliveries", "scraping_jobs", "subscriptions"):
        if _table_exists(table):
            op.drop_table(table)
