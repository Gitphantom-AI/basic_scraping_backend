"""modify user with api key plans

Revision ID: e86777853402
Revises: 62fcf928bb69
Create Date: 2023-12-05 15:52:58.809220

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e86777853402'
down_revision: Union[str, None] = '62fcf928bb69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('api_keys', sa.Column('key_renewal_date', sa.DateTime))
    op.add_column('users', sa.Column('created_date', sa.DateTime))
    op.add_column('users', sa.Column('plan_expires_date', sa.DateTime))
    op.add_column('users', sa.Column('plan', sa.String(4)))
    pass


def downgrade() -> None:
    pass
