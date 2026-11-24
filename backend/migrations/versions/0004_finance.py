"""Account and atomic transaction ledger."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = "0004_finance"
down_revision = "0003_family"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("accounts",
        sa.Column("id",UUID(as_uuid=True),primary_key=True),
        sa.Column("family_id",UUID(as_uuid=True),sa.ForeignKey("families.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("private_owner_id",UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="RESTRICT")),
        sa.Column("name",sa.String(120),nullable=False),
        sa.Column("kind",sa.String(16),nullable=False),
        sa.Column("opening_paise",sa.BigInteger(),nullable=False),
        sa.Column("opening_date",sa.Date(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("family_id","id",name="uq_accounts_family_id_id"),
        sa.CheckConstraint("kind IN ('bank','cash','wallet','credit_card')",name="ck_accounts_kind"),
        sa.CheckConstraint("opening_paise BETWEEN -1000000000000 AND 1000000000000",name="ck_accounts_opening"))
    op.create_index("ix_accounts_family_id","accounts",["family_id"])
    op.create_table("transactions",
        sa.Column("id",UUID(as_uuid=True),primary_key=True),
        sa.Column("family_id",UUID(as_uuid=True),sa.ForeignKey("families.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("account_id",UUID(as_uuid=True),nullable=False),
        sa.Column("destination_id",UUID(as_uuid=True)),
        sa.Column("created_by",UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("request_id",UUID(as_uuid=True),nullable=False),
        sa.Column("kind",sa.String(16),nullable=False),
        sa.Column("amount_paise",sa.BigInteger(),nullable=False),
        sa.Column("occurred_on",sa.Date(),nullable=False),
        sa.Column("category",sa.String(60),nullable=False),
        sa.Column("note",sa.String(300),nullable=False),
        sa.Column("voided_at",sa.DateTime(timezone=True)),
        sa.Column("voided_by",UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="RESTRICT")),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.ForeignKeyConstraint(["family_id","account_id"],["accounts.family_id","accounts.id"],name="fk_transactions_account"),
        sa.ForeignKeyConstraint(["family_id","destination_id"],["accounts.family_id","accounts.id"],name="fk_transactions_destination"),
        sa.CheckConstraint("kind IN ('income','expense','transfer')",name="ck_transactions_kind"),
        sa.CheckConstraint("amount_paise BETWEEN 1 AND 1000000000000",name="ck_transactions_amount"),
        sa.CheckConstraint("(kind = 'transfer' AND destination_id IS NOT NULL AND destination_id <> account_id) OR (kind <> 'transfer' AND destination_id IS NULL)",name="ck_transactions_destination"),
        sa.UniqueConstraint("family_id","created_by","request_id",name="uq_transactions_request"))
    op.create_index("ix_transactions_family_id","transactions",["family_id"])
    op.create_index("ix_transactions_occurred_on","transactions",["occurred_on"])

def downgrade():
    op.drop_table("transactions")
    op.drop_table("accounts")
