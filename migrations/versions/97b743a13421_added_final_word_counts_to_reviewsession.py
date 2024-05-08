"""Added final_word_counts to ReviewSession

Revision ID: 97b743a13421
Revises: 75c5c58486e7
Create Date: 2024-04-30 23:14:32.263991

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '97b743a13421'
down_revision = '75c5c58486e7'
branch_labels = None
depends_on = None


def upgrade():
    # 기존 테이블 삭제 명령 제거
    op.add_column('review_session', sa.Column('final_word_counts', postgresql.JSON(), nullable=True))

def downgrade():
    # 테이블 재생성 명령 제거
    op.drop_column('review_session', 'final_word_counts')

