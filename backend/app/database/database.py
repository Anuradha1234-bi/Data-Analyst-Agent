from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.core.logger import logger


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models."""
    pass


# SQLite requires check_same_thread=False for multithreaded FastAPI requests
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy session.
    Automatically closes the session after request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables defined in metadata."""
    logger.info("Initializing database schema...")
    # Import all models here so they are registered with Base.metadata before create_all
    import app.models.user  # noqa: F401
    import app.models.dataset  # noqa: F401
    import app.models.prediction_run  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")
