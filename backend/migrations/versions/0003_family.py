"""Single-use family invitations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_family"
down_revision = "0002_authentication"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("family_invitations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", UUID(as_uuid=True), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin','member','viewer')", name="ck_family_invitations_role"))
    op.create_index("ix_family_invitations_family_id", "family_invitations", ["family_id"])

def downgrade():
    op.drop_table("family_invitations")
