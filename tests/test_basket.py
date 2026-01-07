import pytest
from typer.testing import CliRunner
from sqlmodel import Session, select
from pharmabot.main import app
from pharmabot.models import BasketItem, ProductCatalog
from pharmabot.services import basket as basket_service

runner = CliRunner()


def test_basket_service_add(session: Session):
    # Setup: Create a product
    product = ProductCatalog(minsan="123456789", name="Test Product")
    session.add(product)
    session.commit()
    session.refresh(product)

    # Test adding item
    item = basket_service.add_item_to_basket(session, product.id, 2)
    assert item.product_id == product.id
    assert item.quantity == 2

    # Test incrementing quantity
    item = basket_service.add_item_to_basket(session, product.id, 3)
    assert item.quantity == 5


def test_basket_service_add_nonexistent_product(session: Session):
    with pytest.raises(basket_service.ProductNotFoundError):
        basket_service.add_item_to_basket(session, 999, 1)


def test_basket_service_update(session: Session):
    # Setup
    product = ProductCatalog(minsan="123456789", name="Test Product")
    session.add(product)
    session.commit()
    session.refresh(product)
    basket_service.add_item_to_basket(session, product.id, 1)

    # Test update
    item = basket_service.update_basket_item_quantity(session, product.id, 10)
    assert item.quantity == 10


def test_basket_service_update_nonexistent_item(session: Session):
    # Setup product but don't add to basket
    product = ProductCatalog(minsan="123456789", name="Test Product")
    session.add(product)
    session.commit()

    with pytest.raises(basket_service.ItemNotPresentError):
        basket_service.update_basket_item_quantity(session, product.id, 10)


def test_basket_service_remove(session: Session):
    # Setup
    product = ProductCatalog(minsan="123456789", name="Test Product")
    session.add(product)
    session.commit()
    session.refresh(product)
    basket_service.add_item_to_basket(session, product.id, 1)

    # Test remove
    basket_service.remove_item_from_basket(session, product.id)
    assert (
        session.exec(
            select(BasketItem).where(BasketItem.product_id == product.id)
        ).first()
        is None
    )


def test_basket_service_remove_nonexistent_item(session: Session):
    # Setup product but don't add to basket
    product = ProductCatalog(minsan="123456789", name="Test Product")
    session.add(product)
    session.commit()

    with pytest.raises(basket_service.ItemNotPresentError):
        basket_service.remove_item_from_basket(session, product.id)


def test_cli_add(session: Session):
    # Setup
    product = ProductCatalog(minsan="A123", name="CLI Product")
    session.add(product)
    session.commit()
    session.refresh(product)

    # Test add command
    result = runner.invoke(app, ["basket", "add", str(product.id), "--quantity", "5"])
    assert result.exit_code == 0
    assert "added to basket" in result.stdout

    # Verify in DB
    item = session.exec(
        select(BasketItem).where(BasketItem.product_id == product.id)
    ).first()
    assert item is not None
    assert item.quantity == 5


def test_cli_add_error(session: Session):
    result = runner.invoke(app, ["basket", "add", "999"])
    assert result.exit_code == 1
    assert "Error" in result.stdout


def test_cli_update(session: Session):
    # Setup
    product = ProductCatalog(minsan="B123", name="Update Product")
    session.add(product)
    session.commit()
    session.refresh(product)
    basket_service.add_item_to_basket(session, product.id, 1)

    # Test update command
    result = runner.invoke(
        app, ["basket", "update", str(product.id), "--quantity", "20"]
    )
    assert result.exit_code == 0
    assert "quantity updated to 20" in result.stdout

    # Verify in DB
    item = session.exec(
        select(BasketItem).where(BasketItem.product_id == product.id)
    ).first()
    assert item.quantity == 20


def test_cli_remove(session: Session):
    # Setup
    product = ProductCatalog(minsan="C123", name="Remove Product")
    session.add(product)
    session.commit()
    session.refresh(product)
    basket_service.add_item_to_basket(session, product.id, 1)

    # Test remove command
    result = runner.invoke(app, ["basket", "remove", str(product.id)])
    assert result.exit_code == 0
    assert "removed from basket" in result.stdout

    # Verify in DB
    item = session.exec(
        select(BasketItem).where(BasketItem.product_id == product.id)
    ).first()
    assert item is None


def test_cli_list(session: Session):
    # Setup
    product1 = ProductCatalog(minsan="L1", name="List Product 1")
    product2 = ProductCatalog(minsan="L2", name="List Product 2")
    session.add(product1)
    session.add(product2)
    session.commit()
    session.refresh(product1)
    session.refresh(product2)

    basket_service.add_item_to_basket(session, product1.id, 5)
    basket_service.add_item_to_basket(session, product2.id, 3)

    # Test list command
    result = runner.invoke(app, ["basket", "list"])
    assert result.exit_code == 0
    assert "L1" in result.stdout
    assert "List Product 1" in result.stdout
    assert "5" in result.stdout
    assert "L2" in result.stdout
    assert "List Product 2" in result.stdout
    assert "3" in result.stdout


def test_cli_list_empty(session: Session):
    result = runner.invoke(app, ["basket", "list"])
    assert result.exit_code == 0
    assert "No items in basket" in result.stdout


def test_basket_service_add_negative_quantity(session: Session):
    product = ProductCatalog(minsan="123456789", name="Test Product")
    session.add(product)
    session.commit()

    with pytest.raises(ValueError):
        basket_service.add_item_to_basket(session, product.id, -1)


def test_basket_service_update_negative_quantity(session: Session):
    product = ProductCatalog(minsan="123456789", name="Test Product")
    session.add(product)
    session.commit()
    session.refresh(product)
    basket_service.add_item_to_basket(session, product.id, 1)

    with pytest.raises(ValueError):
        basket_service.update_basket_item_quantity(session, product.id, 0)
