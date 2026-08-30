"""MySQL engine configuration for the application persistence repository."""

from dataclasses import dataclass
import os

from sqlalchemy import Engine, URL, create_engine


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    database: str
    user: str
    password: str
    pool_size: int
    max_overflow: int


def database_settings() -> DatabaseSettings:
    return DatabaseSettings(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATABASE_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "fit5120"),
        user=os.getenv("MYSQL_USER", "fit5120_app"),
        password=os.getenv("MYSQL_PASSWORD", "change_me"),
        pool_size=int(os.getenv("DATABASE_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
    )


def create_database_engine(settings: DatabaseSettings | None = None) -> Engine:
    selected = settings or database_settings()
    url = URL.create(
        "mysql+pymysql",
        username=selected.user,
        password=selected.password,
        host=selected.host,
        port=selected.port,
        database=selected.database,
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=selected.pool_size,
        max_overflow=selected.max_overflow,
    )
