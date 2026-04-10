from functools import lru_cache

from infra.database import DatabaseConnection, async_session, engine


@lru_cache
def _database_connection_singleton() -> DatabaseConnection:
    return DatabaseConnection(engine=engine, sessionmaker=async_session)


async def get_database_connection() -> DatabaseConnection:
    return _database_connection_singleton()
