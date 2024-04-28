"""Change id type to UUID

Revision ID: 7e40a61c51b3
Revises: 4ef3804dc403
Create Date: 2024-04-26 15:04:58.574369

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as pgUUID


# revision identifiers, used by Alembic.
revision = '7e40a61c51b3'
down_revision = '16b15afc5327'
branch_labels = None
depends_on = None


from alembic import op
import sqlalchemy as sa

def upgrade():
    # 임시 UUID 컬럼 추가
    op.add_column('review_session', sa.Column('new_id', pgUUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE review_session
        SET new_id = md5(random()::text || clock_timestamp()::text)::uuid
    """)
    # 기존 id 컬럼을 삭제하지 않고 새로운 UUID 컬럼을 주 키로 사용
    op.alter_column('review_session', 'new_id', new_column_name='id', existing_type=pgUUID, nullable=False, existing_nullable=True)
    op.create_primary_key("pk_review_session", "review_session", ["id"])
    # 필요한 경우 기존 id 컬럼을 제거
    # op.drop_column('review_session', 'old_id')


def downgrade():
    # UUID 컬럼을 제거하고 기존 정수 id 컬럼을 복원하는 방법에 대해 검토 필요
    op.drop_column('review_session', 'id')
    # 기존 id 컬럼 처리 로직 추가

