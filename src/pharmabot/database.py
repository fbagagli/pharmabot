import os
from sqlmodel import SQLModel, create_engine

# Import models to ensure they are registered with SQLModel.metadata
import pharmabot.models  # noqa: F401

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///pharmabot.db")

engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
