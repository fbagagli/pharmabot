from unittest.mock import patch
from decimal import Decimal
from sqlmodel import Session, select
from pharmabot.models import ProductCatalog, BasketItem, Pharmacy, Offer
from pharmabot.services.scraper import scrape_basket


def test_scrape_basket_logic(session: Session):
    # 1. Setup Data
    product = ProductCatalog(minsan="987654321", name="Test Product")
    session.add(product)
    session.commit()
    session.refresh(product)

    basket_item = BasketItem(product_id=product.id, quantity=1)
    session.add(basket_item)
    session.commit()

    # 2. Mock scrape_product to return dummy offers
    # Note: the actual scraper returns floats for prices as per `clean_price` function
    mock_offers = [
        {
            "pharmacy": "Test Pharmacy 1",
            "price": 10.50,
            "shipping_price": 5.00,
            "free_shipping_over": 50.00,
        },
        {
            "pharmacy": "Test Pharmacy 2",
            "price": 9.99,
            "shipping_price": 0.00,
            "free_shipping_over": None,
        },
    ]

    with patch(
        "pharmabot.services.scraper.scrape_product", return_value=mock_offers
    ) as mock_scrape:
        # 3. Run the function
        scrape_basket(session)

        # 4. Verify interactions
        mock_scrape.assert_called_once_with(query="987654321", headless=True)

    # 5. Verify DB State
    pharmacies = session.exec(select(Pharmacy)).all()
    assert len(pharmacies) == 2

    p1 = next(p for p in pharmacies if p.name == "Test Pharmacy 1")
    # SQLModel/SQLAlchemy converts floats to Decimal for Decimal fields
    assert p1.base_shipping_cost == Decimal("5.00")
    assert p1.free_shipping_threshold == Decimal("50.00")

    p2 = next(p for p in pharmacies if p.name == "Test Pharmacy 2")
    assert p2.base_shipping_cost == Decimal("0.00")
    assert p2.free_shipping_threshold is None

    offers = session.exec(select(Offer)).all()
    assert len(offers) == 2

    o1 = next(o for o in offers if o.pharmacy_id == p1.id)
    assert o1.price == Decimal("10.50")
    assert o1.product_id == product.id

    o2 = next(o for o in offers if o.pharmacy_id == p2.id)
    assert o2.price == Decimal("9.99")
    assert o2.product_id == product.id


def test_scrape_basket_no_minsan(session: Session):
    # 1. Setup Data - Product with NO Minsan
    product = ProductCatalog(minsan=None, name="Generic Aspirin")
    session.add(product)
    session.commit()
    session.refresh(product)

    basket_item = BasketItem(product_id=product.id, quantity=1)
    session.add(basket_item)
    session.commit()

    mock_offers = [
        {
            "pharmacy": "Test Pharmacy A",
            "price": 5.00,
            "shipping_price": 2.00,
            "free_shipping_over": 20.00,
        }
    ]

    with patch(
        "pharmabot.services.scraper.scrape_product", return_value=mock_offers
    ) as mock_scrape:
        # 3. Run the function
        scrape_basket(session)

        # 4. Verify interactions: Should be called with the NAME
        mock_scrape.assert_called_once_with(query="Generic Aspirin", headless=True)

    # 5. Verify DB State
    pharmacy = session.exec(select(Pharmacy).where(Pharmacy.name == "Test Pharmacy A")).first()
    assert pharmacy is not None
    assert pharmacy.base_shipping_cost == Decimal("2.00")

    offer = session.exec(select(Offer).where(Offer.product_id == product.id)).first()
    assert offer is not None
    assert offer.price == Decimal("5.00")
