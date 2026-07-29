"""add user approval_status for signup admin-approval workflow

Revision ID: 125d65df1fe6
Revises: f8f8282cd42a
Create Date: 2026-07-29 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '125d65df1fe6'
down_revision: Union[str, None] = 'f8f8282cd42a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('approval_status', sa.String(length=30), nullable=False, server_default='APPROVED'),
    )
    # Only self-signup rows ever have phone_number set (the admin-create-user
    # form has no such field), so it reliably identifies pre-existing signups
    # that had not verified their e-mail yet under the old flow — leave every
    # other row (including already-verified old signups and all admin-created
    # accounts) at the 'APPROVED' server_default so nobody is retroactively
    # locked out by this migration.
    op.execute(
        "UPDATE users SET approval_status = 'PENDING_EMAIL_VERIFICATION' "
        "WHERE phone_number IS NOT NULL AND email_verified_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column('users', 'approval_status')
