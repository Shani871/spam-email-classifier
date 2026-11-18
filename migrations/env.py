"""Alembic environment. Uses the connection passed by src.db.migrate, or SPAMGUARD_DATABASE_URL."""
from alembic import context
from sqlalchemy import create_engine

from src.db import database_url, metadata

config = context.config


def run(connection):
    context.configure(connection=connection, target_metadata=metadata,
                      render_as_batch=connection.dialect.name == "sqlite", compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    engine = create_engine(config.get_main_option("sqlalchemy.url") or database_url())
    with engine.begin() as new_connection:
        run(new_connection)
