from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5c33c99095d3'
down_revision = '97b743a13421'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('review_session', sa.Column('initial_word_counts', postgresql.JSON(astext_type=sa.Text()), nullable=True))

def downgrade():
    op.drop_column('review_session', 'initial_word_counts')