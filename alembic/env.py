from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys
from dotenv import load_dotenv
from script import db
target_metadata = db.Model.metadata
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# 이 로깅 설정을 `env.py`에 추가하여 마이그레이션 동작을 자세히 추적할 수 있습니다.



# 환경 설정 파일 경로를 Python의 모듈 검색 경로에 추가
sys.path.append(os.getcwd())

# 환경 변수 로드
load_dotenv()

# Alembic Config 객체 접근
config = context.config

# 로깅 설정
fileConfig(config.config_file_name)

# 데이터베이스 URL 환경 변수에서 가져오기
sqlalchemy_url = os.getenv("DATABASE_URL")
config.set_main_option('sqlalchemy.url', sqlalchemy_url)

# 대상 메타데이터 설정
# 주의: 모델의 메타데이터가 필요하다면, 해당 모델을 import하고 메타데이터를 설정해야 합니다.
# 예: from myapp.models import Base; target_metadata = Base.metadata
target_metadata = db.Model.metadata

def run_migrations_offline():
    """Offline 모드에서 마이그레이션 실행"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Online 모드에서 마이그레이션 실행"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
