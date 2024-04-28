"""Add levels and word_sentences columns to review_session table"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as pgUUID

# revision identifiers, used by Alembic.
revision = 'cfdc54e8d400'
down_revision = '7e40a61c51b3'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('review_session', sa.Column('levels', sa.JSON(), nullable=True))
    op.add_column('review_session', sa.Column('word_sentences', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('review_session', 'levels')
    op.drop_column('review_session', 'word_sentences')
