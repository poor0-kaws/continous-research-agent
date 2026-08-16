from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from research_agent.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None = None):  # type: ignore[no-untyped-def]
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Generator[Session]:
    with SessionLocal() as session:
        yield session


def create_schema() -> None:
    from research_agent import models  # noqa: F401

    Base.metadata.create_all(engine)
