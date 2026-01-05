from unittest.mock import patch
from contextlib import contextmanager
from typer.testing import CliRunner
from sqlmodel import Session
from pharmabot.main import app
from pharmabot.models import Product
import pytest


@contextmanager
def mock_get_session_context(session):
    yield session


@pytest.fixture(name="patch_session")
def patch_session_fixture(session):
    with patch(
        "pharmabot.main.get_session",
        side_effect=lambda: mock_get_session_context(session),
    ):
        yield


def test_list_products_empty(session: Session, client: CliRunner, patch_session):
    result = client.invoke(app, ["list-products"])
    assert result.exit_code == 0
    assert "No items are present" in result.stdout


def test_list_products_with_items(session: Session, client: CliRunner, patch_session):
    product1 = Product(minsan="111", name="Product A", quantity=5)
    product2 = Product(minsan="222", name="Product B", quantity=10)
    session.add(product1)
    session.add(product2)
    session.commit()

    result = client.invoke(app, ["list-products"])
    assert result.exit_code == 0
    assert "Minsan" in result.stdout
    assert "Name" in result.stdout
    assert "Quantity" in result.stdout
    assert "111" in result.stdout
    assert "Product A" in result.stdout
    assert "5" in result.stdout
    assert "222" in result.stdout
    assert "Product B" in result.stdout
    assert "10" in result.stdout
