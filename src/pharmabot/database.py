import os
from contextlib import contextmanager
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session

# Import models to ensure they are registered with SQLModel.metadata
import pharmabot.models  # noqa: F401

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///pharmabot.db")

engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
