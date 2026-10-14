from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlmodel import Session, select

from pharmabot.models import BasketItem, Offer, Pharmacy, ProductCatalog
from pharmabot.services.scraper import clear_database, scrape_basket
from pharmabot.services.scraping.base import ScrapedOffer


def test_scrape_basket_logic(session: Session):
    # 1. Setup Data
    product = ProductCatalog(minsan="987654321", name="Test Product")
    session.add(product)
    session.commit()
    session.refresh(product)

    basket_item = BasketItem(product_id=product.id, quantity=1)
    session.add(basket_item)
    session.commit()

    # 2. Mock provider to return dummy offers
    mock_offers = [
        ScrapedOffer(
            pharmacy_name="Test Pharmacy 1",
            price=Decimal("10.50"),
            shipping_price=Decimal("5.00"),
            free_shipping_over=Decimal("50.00"),
        ),
        ScrapedOffer(
            pharmacy_name="Test Pharmacy 2",
            price=Decimal("9.99"),
            shipping_price=Decimal("0.00"),
            free_shipping_over=None,
        ),
    ]

    mock_provider = MagicMock()
    mock_provider.scrape.return_value = mock_offers

    with patch(
        "pharmabot.services.scraper.get_scraper_provider", return_value=mock_provider
    ) as mock_get_provider:
        # 3. Run the function
        created_offers = scrape_basket(
            session, provider_name="prezzifarmaco", incremental=True
        )

        # 4. Verify interactions
        mock_get_provider.assert_called_once_with("prezzifarmaco")
        mock_provider.scrape.assert_called_once_with("987654321")
        assert len(created_offers) == 2

    # 5. Verify DB State
    pharmacies = session.exec(select(Pharmacy)).all()
    assert len(pharmacies) == 2

    p1 = next(p for p in pharmacies if p.name == "Test Pharmacy 1")
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
        ScrapedOffer(
            pharmacy_name="Test Pharmacy A",
            price=Decimal("5.00"),
            shipping_price=Decimal("2.00"),
            free_shipping_over=Decimal("20.00"),
        )
    ]

    mock_provider = MagicMock()
    mock_provider.scrape.return_value = mock_offers

    with patch(
        "pharmabot.services.scraper.get_scraper_provider", return_value=mock_provider
    ):
        # 3. Run the function
        created_offers = scrape_basket(
            session, provider_name="prezzifarmaco", incremental=True
        )

        # 4. Verify interactions: Should be called with the NAME
        mock_provider.scrape.assert_called_once_with("Generic Aspirin")
        assert len(created_offers) == 1

    # 5. Verify DB State
    pharmacy = session.exec(
        select(Pharmacy).where(Pharmacy.name == "Test Pharmacy A")
    ).first()
    assert pharmacy is not None
    assert pharmacy.base_shipping_cost == Decimal("2.00")

    offer = session.exec(select(Offer).where(Offer.product_id == product.id)).first()
    assert offer is not None
    assert offer.price == Decimal("5.00")


def test_scrape_basket_empty(session: Session):
    # Test that scraping an empty basket returns []
    offers = scrape_basket(session, provider_name="prezzifarmaco", incremental=True)
    assert offers == []


def test_scrape_basket_incremental_skips_existing(session: Session):
    # Setup two products, one with existing offers
    p1 = ProductCatalog(name="Product 1", minsan="111")
    p2 = ProductCatalog(name="Product 2", minsan="222")
    session.add(p1)
    session.add(p2)
    session.commit()
    session.refresh(p1)
    session.refresh(p2)

    session.add(BasketItem(product_id=p1.id, quantity=1))
    session.add(BasketItem(product_id=p2.id, quantity=1))

    pharmacy = Pharmacy(name="Existing Pharmacy", base_shipping_cost=Decimal("5.00"))
    session.add(pharmacy)
    session.commit()
    session.refresh(pharmacy)

    session.add(
        Offer(price=Decimal("10.00"), pharmacy_id=pharmacy.id, product_id=p1.id)
    )
    session.commit()

    mock_provider = MagicMock()
    mock_provider.scrape.return_value = [
        ScrapedOffer(
            pharmacy_name="New Pharmacy",
            price=Decimal("20.00"),
            shipping_price=Decimal("0.00"),
            free_shipping_over=None,
        )
    ]

    with patch(
        "pharmabot.services.scraper.get_scraper_provider", return_value=mock_provider
    ):
        created = scrape_basket(
            session, provider_name="prezzifarmaco", incremental=True
        )
        # Should only scrape for p2
        mock_provider.scrape.assert_called_once_with("222")
        assert len(created) == 1

    # Verify both products have offers in DB
    p1_offers = session.exec(select(Offer).where(Offer.product_id == p1.id)).all()
    p2_offers = session.exec(select(Offer).where(Offer.product_id == p2.id)).all()
    assert len(p1_offers) == 1
    assert len(p2_offers) == 1


def test_clear_database(session: Session):
    pharmacy = Pharmacy(name="Test Pharmacy", base_shipping_cost=Decimal("5.00"))
    session.add(pharmacy)
    session.commit()
    session.refresh(pharmacy)

    product = ProductCatalog(name="Test Product", minsan="123")
    session.add(product)
    session.commit()
    session.refresh(product)

    offer = Offer(
        price=Decimal("10.00"), pharmacy_id=pharmacy.id, product_id=product.id
    )
    session.add(offer)
    session.commit()

    assert len(session.exec(select(Offer)).all()) == 1
    assert len(session.exec(select(Pharmacy)).all()) == 1

    clear_database(session)

    assert len(session.exec(select(Offer)).all()) == 0
    assert len(session.exec(select(Pharmacy)).all()) == 0
