from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = '5c33c99095d4'
down_revision = '5c33c99095d3'  # 이전 리비전 ID를 여기에 넣습니다.
branch_labels = None
depends_on = None

def upgrade():
    # Add the new column to the review_session table
    op.add_column('review_session', sa.Column('word_review_status', sa.JSON(), nullable=True))

def downgrade():
    # Remove the column in case of downgrade
    op.drop_column('review_session', 'word_review_status')
