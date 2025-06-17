from logging.config import fileConfig
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from alembic import context
from sqlmodel import SQLModel
from fastapi_auth.database import DATABASE_URL
from fastapi_auth.models import *

config = context.config
fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()
        

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():

    connectable: AsyncEngine = create_async_engine(DATABASE_URL, echo=True)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
