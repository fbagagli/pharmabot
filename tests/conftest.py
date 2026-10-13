import pytest
from unittest.mock import patch
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
from contextlib import contextmanager

# Import models to ensure they are registered
import pharmabot.models  # noqa: F401


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def override_get_session(session):
    with patch("pharmabot.database.get_session") as mock_get_session:

        @contextmanager
        def mock_gen():
            yield session

        mock_get_session.side_effect = mock_gen
        yield


@pytest.fixture(autouse=True)
def mock_browser_session():
    with patch("pharmabot.services.scraper.get_browser_session") as mock_get_sb:
        from unittest.mock import MagicMock

        mock_sb = MagicMock()
        mock_get_sb.return_value.__enter__.return_value = mock_sb
        yield mock_sb
