"""Database setup and session helpers."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """
    Provide the declarative SQLAlchemy base.

    Returns:
    --------
        Base:
            Base class for ORM models.
    """


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """
    Yield one database session for a request.

    Returns:
    --------
        Generator[Session, None, None]:
            SQLAlchemy session generator.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database() -> None:
    """
    Create database tables.

    Returns:
    --------
        None:
            Tables are created when missing.
    """

    Base.metadata.create_all(bind=engine)
