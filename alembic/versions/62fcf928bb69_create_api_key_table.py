"""Create API key table

Revision ID: 62fcf928bb69
Revises: 
Create Date: 2023-11-21 11:21:22.663572

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62fcf928bb69'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key', sa.String(32), nullable=False),
        sa.Column('charge', sa.Integer),
        sa.Column('owner_id', sa.Integer, sa.ForeignKey("users.id")),
    )


def downgrade() -> None:
    pass
