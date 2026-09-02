"""Add booking reminder setting.

Revision ID: b7c8d9e0f1a2
Revises: dc04d9e712dd
Create Date: 2026-08-31 18:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'dc04d9e712dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add optional reminder interval to bookings."""
    op.add_column(
        'bookings',
        sa.Column(
            'reminder_minutes_before',
            sa.Integer(),
            server_default='180',
            nullable=True,
        ),
    )
    op.create_check_constraint(
        'check_booking_reminder_minutes_positive',
        'bookings',
        'reminder_minutes_before IS NULL OR reminder_minutes_before > 0',
    )


def downgrade() -> None:
    """Remove reminder interval from bookings."""
    op.drop_constraint(
        'check_booking_reminder_minutes_positive',
        'bookings',
        type_='check',
    )
    op.drop_column('bookings', 'reminder_minutes_before')
