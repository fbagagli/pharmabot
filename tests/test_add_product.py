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


def test_add_product_new_valid(session: Session, client: CliRunner, patch_session):
    result = client.invoke(
        app, ["add-product", "12345", "--name", "Aspirin", "--quantity", "10"]
    )
    assert result.exit_code == 0
    assert "Added product: Aspirin" in result.stdout

    product = session.get(Product, "12345")
    assert product is not None
    assert product.name == "Aspirin"
    assert product.quantity == 10


def test_add_product_new_default_quantity(
    session: Session, client: CliRunner, patch_session
):
    result = client.invoke(app, ["add-product", "67890", "--name", "Tachipirina"])
    assert result.exit_code == 0

    product = session.get(Product, "67890")
    assert product is not None
    assert product.name == "Tachipirina"
    assert product.quantity == 1


def test_add_product_missing_name(session: Session, client: CliRunner, patch_session):
    result = client.invoke(app, ["add-product", "11111"])
    assert result.exit_code == 1
    assert "Name is required for new products" in result.stdout


def test_add_product_update_name(session: Session, client: CliRunner, patch_session):
    # Setup existing product
    product = Product(minsan="22222", name="Old Name", quantity=5)
    session.add(product)
    session.commit()

    result = client.invoke(app, ["add-product", "22222", "--name", "New Name"])
    assert result.exit_code == 0
    assert "Updated product" in result.stdout

    session.refresh(product)
    assert product.name == "New Name"
    assert product.quantity == 5


def test_add_product_update_quantity(
    session: Session, client: CliRunner, patch_session
):
    # Setup existing product
    product = Product(minsan="33333", name="Drug A", quantity=10)
    session.add(product)
    session.commit()

    result = client.invoke(app, ["add-product", "33333", "--quantity", "5"])
    assert result.exit_code == 0

    session.refresh(product)
    assert product.quantity == 15  # 10 + 5


def test_add_product_update_both(session: Session, client: CliRunner, patch_session):
    # Setup existing product
    product = Product(minsan="44444", name="Drug B", quantity=2)
    session.add(product)
    session.commit()

    result = client.invoke(
        app, ["add-product", "44444", "--name", "Drug B v2", "--quantity", "3"]
    )
    assert result.exit_code == 0

    session.refresh(product)
    assert product.name == "Drug B v2"
    assert product.quantity == 5  # 2 + 3


def test_add_product_invalid_quantity(
    session: Session, client: CliRunner, patch_session
):
    result = client.invoke(
        app, ["add-product", "55555", "--name", "Bad Qty", "--quantity", "0"]
    )
    assert result.exit_code == 1
    assert "Quantity must be a positive integer" in result.stdout

    result_neg = client.invoke(
        app, ["add-product", "55555", "--name", "Bad Qty", "--quantity", "-1"]
    )
    assert result_neg.exit_code == 1
