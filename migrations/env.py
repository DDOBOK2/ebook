from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from logging.config import fileConfig
from alembic import context
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
db = SQLAlchemy(app)

config = context.config
fileConfig(config.config_file_name)
target_metadata = db.metadata

def run_migrations_offline():
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
    with app.app_context():
        connectable = db.engine
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
