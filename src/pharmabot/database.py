import os
from contextlib import contextmanager
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session

# Import models to ensure they are registered with SQLModel.metadata
import pharmabot.models  # noqa: F401

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///pharmabot.db")

engine = create_engine(DATABASE_URL)

# Flag to track if the database has been explicitly initialized (for GUI)
_is_connected = False


def is_connected() -> bool:
    """Check if the database has been connected via the GUI."""
    return _is_connected


def init_db(path: str) -> None:
    """Initialize the database connection with the given path."""
    global engine, _is_connected

    # Construct the database URL
    # Ensure it's a valid SQLite path
    db_url = f"sqlite:///{path}"

    # Create new engine
    engine = create_engine(db_url)

    # Create tables
    create_db_and_tables()

    _is_connected = True


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
