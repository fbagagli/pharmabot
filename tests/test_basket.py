import pytest
from decimal import Decimal
from typer.testing import CliRunner
from sqlmodel import Session, select
from pharmabot.main import app
from pharmabot.models import BasketItem, ProductCatalog, Pharmacy, Offer
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
    assert str(product1.id) in result.stdout
    assert "L1" in result.stdout
    assert "List Product 1" in result.stdout
    assert "5" in result.stdout
    assert str(product2.id) in result.stdout
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


def test_cli_optimize(session: Session):
    # Setup data
    p1 = ProductCatalog(minsan="900000001", name="Product A")
    session.add(p1)
    session.commit()
    session.refresh(p1)

    basket_service.add_item_to_basket(session, p1.id, 2)

    ph1 = Pharmacy(
        name="Pharma One",
        base_shipping_cost=Decimal("10.00"),
        free_shipping_threshold=Decimal("100.00"),
    )
    session.add(ph1)
    session.commit()
    session.refresh(ph1)

    o1 = Offer(price=Decimal("10.00"), pharmacy_id=ph1.id, product_id=p1.id)
    session.add(o1)
    session.commit()

    # Test optimize command
    result = runner.invoke(app, ["basket", "optimize"])
    assert result.exit_code == 0
    # Updated Output Checks
    assert "Solutions with 1 Order" in result.stdout
    assert "Pharma One" in result.stdout
    assert "€ 20.00" in result.stdout  # Items 2*10
    assert "€ 10.00" in result.stdout  # Shipping
    assert "€ 30.00" in result.stdout  # Total
    assert "Base: €10.00" in result.stdout
    # Check for free shipping info separately in case of line wrapping
    assert "€100.00" in result.stdout


def test_cli_optimize_multi(session: Session):
    # P1: A ($20), B ($20) + Ship $5 = $45
    # P2: A ($5) + Ship $0 (Free > 4) = $5
    # P3: B ($5) + Ship $0 (Free > 4) = $5
    # P2+P3 = $10.

    p1 = Pharmacy(
        name="P1",
        base_shipping_cost=Decimal("5"),
        free_shipping_threshold=Decimal("100"),
    )
    p2 = Pharmacy(
        name="P2", base_shipping_cost=Decimal("5"), free_shipping_threshold=Decimal("4")
    )
    p3 = Pharmacy(
        name="P3", base_shipping_cost=Decimal("5"), free_shipping_threshold=Decimal("4")
    )
    session.add(p1)
    session.add(p2)
    session.add(p3)

    prodA = ProductCatalog(name="ItemA")
    prodB = ProductCatalog(name="ItemB")
    session.add(prodA)
    session.add(prodB)
    session.commit()

    session.add(Offer(pharmacy_id=p1.id, product_id=prodA.id, price=Decimal("20")))
    session.add(Offer(pharmacy_id=p1.id, product_id=prodB.id, price=Decimal("20")))
    session.add(Offer(pharmacy_id=p2.id, product_id=prodA.id, price=Decimal("5")))
    session.add(Offer(pharmacy_id=p3.id, product_id=prodB.id, price=Decimal("5")))

    session.add(BasketItem(product_id=prodA.id, quantity=1))
    session.add(BasketItem(product_id=prodB.id, quantity=1))
    session.commit()

    # Test with max-orders=2
    result = runner.invoke(app, ["basket", "optimize", "--max-orders", "2"])

    assert result.exit_code == 0
    assert "Solutions with 2 Orders" in result.stdout
    # Should find 10.00
    assert "€ 10.00" in result.stdout
    # Should list P2 and P3
    assert "P2" in result.stdout
    assert "P3" in result.stdout
