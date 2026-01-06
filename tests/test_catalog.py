from typer.testing import CliRunner
from sqlmodel import Session, select
from pharmabot.main import app
from pharmabot.models import ProductCatalog, BasketItem

runner = CliRunner()


def test_add_product(session: Session):
    result = runner.invoke(app, ["catalog", "add", "123456", "--name", "Test Product"])
    assert result.exit_code == 0
    assert "Product 123456 added successfully." in result.stdout

    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.minsan == "123456")
    ).first()
    assert product is not None
    assert product.name == "Test Product"


def test_add_duplicate_product(session: Session):
    # Add first time
    runner.invoke(app, ["catalog", "add", "123456", "--name", "Test Product"])

    # Add duplicate
    result = runner.invoke(
        app, ["catalog", "add", "123456", "--name", "Duplicate Product"]
    )
    assert result.exit_code == 1
    assert "Error: Product with minsan 123456 already exists" in result.stdout


def test_list_products_empty(session: Session):
    result = runner.invoke(app, ["catalog", "list"])
    assert result.exit_code == 0
    assert "Product Catalog" in result.stdout
    assert "Minsan" in result.stdout
    assert "Name" in result.stdout


def test_list_products_populated(session: Session):
    runner.invoke(app, ["catalog", "add", "123456", "--name", "Product A"])
    runner.invoke(app, ["catalog", "add", "789012", "--name", "Product B"])

    result = runner.invoke(app, ["catalog", "list"])
    assert result.exit_code == 0
    assert "123456" in result.stdout
    assert "Product A" in result.stdout
    assert "789012" in result.stdout
    assert "Product B" in result.stdout


def test_update_product(session: Session):
    runner.invoke(app, ["catalog", "add", "123456", "--name", "Old Name"])

    result = runner.invoke(app, ["catalog", "update", "123456", "--name", "New Name"])
    assert result.exit_code == 0
    assert "Product 123456 updated successfully." in result.stdout

    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.minsan == "123456")
    ).first()
    assert product.name == "New Name"


def test_update_non_existent_product(session: Session):
    result = runner.invoke(app, ["catalog", "update", "999999", "--name", "New Name"])
    assert result.exit_code == 1
    assert "Error: Product with minsan 999999 not found" in result.stdout


def test_remove_product(session: Session):
    runner.invoke(app, ["catalog", "add", "123456", "--name", "To Remove"])

    result = runner.invoke(app, ["catalog", "remove", "123456"])
    assert result.exit_code == 0
    assert "Product 123456 removed successfully." in result.stdout

    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.minsan == "123456")
    ).first()
    assert product is None


def test_remove_non_existent_product(session: Session):
    result = runner.invoke(app, ["catalog", "remove", "999999"])
    assert result.exit_code == 1
    assert "Error: Product with minsan 999999 not found" in result.stdout


def test_remove_product_cascade_basket(session: Session):
    # Setup: Add product and add to basket (manually since we don't have basket CLI yet, or maybe we do?)
    # Wait, the prompt says "Basket Item will be the subset of product that will be put in a basket".
    # I should manually insert into BasketItem to test cascade.

    runner.invoke(app, ["catalog", "add", "123456", "--name", "Product In Basket"])
    product = session.exec(
        select(ProductCatalog).where(ProductCatalog.minsan == "123456")
    ).first()

    basket_item = BasketItem(product_id=product.id, quantity=5)
    session.add(basket_item)
    session.commit()

    # Verify basket item exists
    assert (
        session.exec(
            select(BasketItem).where(BasketItem.product_id == product.id)
        ).first()
        is not None
    )

    # Remove product
    result = runner.invoke(app, ["catalog", "remove", "123456"])
    assert result.exit_code == 0

    # Verify product removed
    assert (
        session.exec(
            select(ProductCatalog).where(ProductCatalog.minsan == "123456")
        ).first()
        is None
    )

    # Verify basket item removed
    assert (
        session.exec(
            select(BasketItem).where(BasketItem.product_id == product.id)
        ).first()
        is None
    )
