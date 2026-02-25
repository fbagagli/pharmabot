import pytest
from unittest.mock import patch, MagicMock
from sqlmodel import Session, select
from pharmabot.models import ProductCatalog, BasketItem, Offer, Pharmacy
from pharmabot.services.scraper import scrape_basket, clear_database

def test_clear_database(session: Session):
    # Setup: add some data
    pharmacy = Pharmacy(name="Test Pharmacy", base_shipping_cost=5.0)
    session.add(pharmacy)
    session.commit()
    session.refresh(pharmacy)

    product = ProductCatalog(name="Test Product", minsan="123")
    session.add(product)
    session.commit()
    session.refresh(product)

    offer = Offer(price=10.0, pharmacy_id=pharmacy.id, product_id=product.id)
    session.add(offer)
    session.commit()

    # Verify data exists
    assert len(session.exec(select(Offer)).all()) == 1
    assert len(session.exec(select(Pharmacy)).all()) == 1

    # Run clear
    clear_database(session)

    # Verify data is gone
    assert len(session.exec(select(Offer)).all()) == 0
    assert len(session.exec(select(Pharmacy)).all()) == 0

def test_scrape_basket_skips_existing(session: Session):
    # Setup: add two products to basket, one already has offers
    p1 = ProductCatalog(name="Product 1", minsan="111")
    p2 = ProductCatalog(name="Product 2", minsan="222")
    session.add(p1)
    session.add(p2)
    session.commit()
    session.refresh(p1)
    session.refresh(p2)

    session.add(BasketItem(product_id=p1.id, quantity=1))
    session.add(BasketItem(product_id=p2.id, quantity=1))

    pharmacy = Pharmacy(name="Existing Pharmacy", base_shipping_cost=5.0)
    session.add(pharmacy)
    session.commit()
    session.refresh(pharmacy)

    # Add offer for p1
    session.add(Offer(price=10.0, pharmacy_id=pharmacy.id, product_id=p1.id))
    session.commit()

    # Mock scrape_product
    with patch("pharmabot.services.scraper.scrape_product") as mock_scrape:
        mock_scrape.return_value = [{"pharmacy": "New Pharmacy", "price": 20.0, "shipping_price": 0.0, "free_shipping_over": None}]

        scrape_basket(session, headless=True)

        # Verify scrape_product was called ONLY for p2
        assert mock_scrape.call_count == 1
        mock_scrape.assert_called_once_with(query="222", headless=True, wait_for_input=True)

    # Verify we now have offers for both
    assert len(session.exec(select(Offer).where(Offer.product_id == p1.id)).all()) == 1
    assert len(session.exec(select(Offer).where(Offer.product_id == p2.id)).all()) == 1
