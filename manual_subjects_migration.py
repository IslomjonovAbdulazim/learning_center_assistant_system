"""Manual migration to add subjects table"""

revision = '28b3e44b6539'
down_revision = '1f2eeb35e231'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Create subjects table
    op.create_table('subjects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('learning_center_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['learning_center_id'], ['learning_centers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subjects_id'), 'subjects', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_subjects_id'), table_name='subjects')
    op.drop_table('subjects')