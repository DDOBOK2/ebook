"""Add deleted_sentences to ReviewSession

Revision ID: 4e7bedd57080
Revises: 5c33c99095d3
Create Date: 2024-05-08 00:11:25.133233

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4e7bedd57080'
down_revision = '5c33c99095d3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('review_session')
    op.drop_table('user')
    op.drop_table('sessions')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('sessions',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('session_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('data', postgresql.BYTEA(), autoincrement=False, nullable=True),
    sa.Column('expiry', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name='sessions_pkey'),
    sa.UniqueConstraint('session_id', name='sessions_session_id_key')
    )
    op.create_table('user',
    sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('user_id_seq'::regclass)"), autoincrement=True, nullable=False),
    sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name='user_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_table('review_session',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), autoincrement=False, nullable=False),
    sa.Column('ebook_title', sa.VARCHAR(length=150), autoincrement=False, nullable=False),
    sa.Column('review_text', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=True),
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('review_stage', sa.VARCHAR(length=50), server_default=sa.text("'not_reviewed'::character varying"), autoincrement=False, nullable=False),
    sa.Column('levels', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('word_sentences', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('final_word_counts', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('initial_word_counts', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='review_session_user_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='review_session_pkey')
    )
    # ### end Alembic commands ###
