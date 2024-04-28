from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.dialects import postgresql

revision = '75c5c58486e7'
down_revision = 'cfdc54e8d400'
branch_labels = None
depends_on = None

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('sessions',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('session_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('data', postgresql.BYTEA(), autoincrement=False, nullable=True),
    sa.Column('expiry', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name='sessions_pkey'),
    sa.UniqueConstraint('session_id', name='sessions_session_id_key')
    )
    op.create_table('review_session',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('ebook_title', sa.VARCHAR(length=150), autoincrement=False, nullable=False),
    sa.Column('review_text', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('review_stage', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('levels', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('word_sentences', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name='review_session_pkey')
    )
    # ### end Alembic commands ###

def downgrade():
    conn = op.get_bind()
    # Direct SQL to check if the table exists
    res = conn.execute("SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'sessions');")
    exists = res.fetchone()[0]
    
    if not exists:
        op.create_table('sessions',
            sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
            sa.Column('session_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
            sa.Column('data', sa.BYTEA(), autoincrement=False, nullable=True),
            sa.Column('expiry', sa.TIMESTAMP(), autoincrement=False, nullable=True),
            sa.PrimaryKeyConstraint('id', name='sessions_pkey'),
            sa.UniqueConstraint('session_id', name='sessions_session_id_key')
        )
